"""The Codex/ChatGPT subscription path (PRD F8).

The app asks the Codex CLI itself for the picture. Codex has a built-in, stable
`image_generation` feature (checked on codex-cli 0.160.1): its `image_gen` tool runs under the
user's `codex login` and saves a PNG under `$CODEX_HOME/generated_images/<thread id>/`. The app
runs one `codex exec` turn per image with the prompt on stdin, in an empty scratch folder, with a
read-only sandbox, without the user's Codex config or rules, and without saving the session. It
then finds the saved PNG from the turn's JSON events or that folder.

The app never reads, stores or exports the login token (it only checks that the login file
exists, and `codex login status` in the check), requests run strictly one at a time (parallel
calls racing the token refresh invalidated the credential in Darling Blades), an authentication
error stops the Codex queue until the user signs in again, the raw output stays on disk until it
passes the image check, and nothing is retried automatically.
"""
import asyncio
import json
import os
import shutil
import tempfile
import time
from pathlib import Path

from dungeon import subprocesses
from dungeon.images.adapters.base import AdapterError, Check, ImageResult, media_type

TIMEOUT_SECONDS = 600
VERIFIED_SIZES = {(1024, 1024), (1536, 1024), (1024, 1536)}
LOGIN_STEP = 'Run "codex login" in a terminal on this computer, then choose "Signed in again" in Settings.'
AUTH_SIGNS = ('auth.json', 'codex login', 'not logged in', 'access_token', 'refresh_token', 'token refresh',
              'http 401', 'http 403', '401 unauthorized', 'unauthorized', 'reauthentication', 'sign in again')
REFUSAL_SIGNS = ('content policy', 'content_policy', 'safety system', 'moderation', 'policy violation')
PROMPT = ('Use your built-in image generation tool to create exactly one {width}x{height} image from the '
          'description below. Do not run shell commands, read or edit files, or ask questions. After the '
          'image is generated, reply with the single word DONE.\n\nDescription:\n{prompt}\n\nAvoid: {negative}')
SERIAL = asyncio.Lock()


def codex_home() -> Path:
    return Path(os.environ.get('CODEX_HOME') or Path.home() / '.codex')


def logged_in() -> bool:
    return (codex_home() / 'auth.json').is_file()


def locate(config) -> str | None:
    configured = (config.get('cli_path') or '').strip()
    # A location saved for the retired chatgpt-imagegen method is not a Codex CLI.
    if configured and 'imagegen' not in Path(configured).name.casefold():
        return configured if Path(configured).is_file() else None
    return shutil.which('codex')


def failure(text: str) -> AdapterError:
    lines = [line for line in text.strip().splitlines() if line.strip()]
    last = lines[-1][:300] if lines else 'no error output'
    lowered = text.casefold()
    if any(sign in lowered for sign in AUTH_SIGNS):
        return AdapterError('auth', f'Codex sign-in failed or expired ({last}). The Codex queue is stopped. '
                            f'{LOGIN_STEP}')
    if any(sign in lowered for sign in REFUSAL_SIGNS):
        return AdapterError('refused', f'OpenAI refused this image ({last}).')
    if 'http 429' in lowered or 'usage limit' in lowered or 'rate limit' in lowered:
        return AdapterError('rate_limited', 'Your ChatGPT image quota is used up for now. Try again later.')
    if 'timed out' in lowered or 'stalled' in lowered:
        return AdapterError('timeout', f'Codex image generation timed out ({last}).')
    return AdapterError('failed', f'Codex image generation failed: {last}')


def events(stdout: str) -> list[dict]:
    parsed = []
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict):
            parsed.append(event)
    return parsed


def saved_paths(value) -> list[str]:
    """Every `saved_path` anywhere in an event, whatever item shape this Codex version uses."""
    if isinstance(value, dict):
        found = [value['saved_path']] if isinstance(value.get('saved_path'), str) else []
        return found + [path for item in value.values() for path in saved_paths(item)]
    if isinstance(value, list):
        return [path for item in value for path in saved_paths(item)]
    return []


def turn_errors(parsed) -> str:
    """Final errors only: Codex also reports reconnect attempts as `error` events."""
    messages = []
    for event in parsed:
        if event.get('type') == 'turn.failed':
            messages.append(str((event.get('error') or {}).get('message') or event))
        elif event.get('type') == 'error' and not str(event.get('message', '')).startswith('Reconnecting'):
            messages.append(str(event.get('message')))
    return '\n'.join(messages)


def find_image(parsed, started: float) -> Path | None:
    for path in reversed([path for event in parsed for path in saved_paths(event)]):
        if Path(path).is_file():
            return Path(path)
    root = codex_home() / 'generated_images'
    thread = next((event.get('thread_id') for event in parsed if event.get('type') == 'thread.started'), None)
    folders = [root / thread] if thread else []
    for folder in [*folders, root]:
        if folder.is_dir():
            # Requests are serial, so a PNG written since this one started is its output. No slack: the turn just
            # before (a character sheet made for this picture) finished less than a second earlier.
            fresh = [path for path in folder.rglob('*.png') if path.stat().st_mtime >= started]
            if fresh:
                return max(fresh, key=lambda path: path.stat().st_mtime)
    return None


class CodexAdapter:
    def __init__(self, timeout_seconds=None):
        self.timeout_seconds = timeout_seconds

    def budget(self) -> int:
        return self.timeout_seconds or TIMEOUT_SECONDS

    async def generate(self, request) -> ImageResult:
        cli = locate(request.config)
        if cli is None:
            raise AdapterError('unavailable', 'The Codex CLI was not found. Install it or set its location in Settings.')
        if not logged_in():
            raise AdapterError('auth', f'Codex is not signed in on this computer. {LOGIN_STEP}')
        if (request.width, request.height) not in VERIFIED_SIZES:
            raise AdapterError('incompatible', 'Codex only makes 1024x1024, 1536x1024 or 1024x1536 images.')
        async with SERIAL:
            return await self.native(cli, request)

    async def native(self, cli, request) -> ImageResult:
        raw = request.raw_dir / f'{request.job_id}.png'
        prompt = PROMPT.format(width=request.width, height=request.height, prompt=request.prompt,
                               negative=request.negative or 'nothing in particular')
        with tempfile.TemporaryDirectory(prefix='companion-codex-') as scratch:
            attach = []
            if request.reference is not None:
                # The picture to follow is attached to the prompt; `--image` comes before the
                # other options so it never swallows the `-` that reads the prompt from stdin.
                extension, _kind = media_type(request.reference)
                picture = Path(scratch) / f'reference.{extension}'
                picture.write_bytes(request.reference)
                attach = ['--image', str(picture)]
            args = [cli, 'exec', *attach, '--json', '--skip-git-repo-check', '--ephemeral',
                    '--ignore-user-config', '--ignore-rules', '--sandbox', 'read-only', '--cd', scratch, '-']
            started = time.time()
            returncode, stdout, stderr = await self.run(args, prompt.encode('utf-8'), self.budget())
        parsed = events(stdout)
        image = find_image(parsed, started)
        if image is None:
            raise failure('\n'.join(filter(None, [turn_errors(parsed), stderr if returncode else '']))
                          or 'Codex finished without generating an image.')
        shutil.copyfile(image, raw)
        thread = next((event.get('thread_id') for event in parsed if event.get('type') == 'thread.started'), None)
        return ImageResult(raw.read_bytes(), model='Codex image_gen', workflow='codex exec', raw_path=raw,
                           remote_id=thread)

    async def run(self, args, stdin: bytes | None, budget) -> tuple[int, str, str]:
        process = await subprocesses.start(
            *args, stdin=asyncio.subprocess.PIPE if stdin is not None else asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        try:
            async with asyncio.timeout(budget + 30):
                stdout, stderr = await process.communicate(stdin)
        except TimeoutError as error:
            await self.stop(process)
            raise AdapterError('timeout', 'Codex image generation did not finish in time; it was stopped.') from error
        except asyncio.CancelledError:
            await self.stop(process)
            raise
        return process.returncode, stdout.decode('utf-8', 'replace'), stderr.decode('utf-8', 'replace')

    @staticmethod
    async def stop(process):
        """Stops only the process this app started."""
        if process.returncode is None:
            process.kill()
            await process.wait()

    async def output(self, args) -> str:
        process = await subprocesses.start(*args, stdin=asyncio.subprocess.DEVNULL,
                                           stdout=asyncio.subprocess.PIPE,
                                           stderr=asyncio.subprocess.STDOUT)
        try:
            async with asyncio.timeout(20):
                stdout, _ = await process.communicate()
        except TimeoutError:
            await self.stop(process)
            raise
        return stdout.decode('utf-8', 'replace').strip()

    async def check(self, backend, config, key=None) -> Check:
        """Finds the CLI, reads its version and sign-in state; sends no prompt and spends no quota."""
        cli = locate(config)
        if cli is None:
            return Check(False, 'The Codex CLI was not found.',
                         ['Install it with "npm i -g @openai/codex", or enter the full path to codex.'])
        details = [f'CLI: {cli}']
        try:
            details.append(await self.output([cli, '--version']) or 'version unknown')
            status = await self.output([cli, 'login', 'status'])
            details.append(status.splitlines()[-1] if status else 'sign-in state unknown')
        except (OSError, TimeoutError):
            return Check(False, 'The CLI could not be started.', details)
        if not logged_in() or 'not logged in' in details[-1].casefold():
            return Check(False, 'Codex is not signed in on this computer.', [*details, LOGIN_STEP])
        if 'api key' in details[-1].casefold():
            return Check(True, 'Codex is signed in with an API key, so images are billed to that key, not your '
                         'ChatGPT plan. Run "codex login" to use your plan instead.', details)
        return Check(True, 'The CLI is installed and a Codex login exists. This path is experimental.', details)
