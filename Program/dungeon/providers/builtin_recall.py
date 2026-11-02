"""Built-in recall: a llama.cpp server the Dungeon starts on this PC for embeddings (PRD M10).

The user downloads an embedding model file (GGUF) themselves, so they accept its terms; the Dungeon
only suggests models. The llama.cpp runtime is downloaded on request from a pinned release and checked
against its SHA-256. The server runs in its own process on a private loopback port, CPU only, with a few
threads, so it never competes with a chat model or ComfyUI for the GPU. Models stay outside the
Companion's own process, as they always have. A guard process (`embedding_guard.py`) stops the server
when the Dungeon goes away, even if it was killed.
"""
import asyncio
import hashlib
import os
import platform
import shutil
import socket
import subprocess
import sys
import tarfile
import time
import zipfile
from pathlib import Path

import httpx

from dungeon.database import one
from dungeon.errors import DomainError, require

RUNTIME_TAG = 'b11457'
RELEASES = 'https://github.com/ggml-org/llama.cpp/releases/download'
# Platform -> (asset, bytes, sha256). Checked by hand against the release on 2026-10-07.
RUNTIMES = {
    'windows-x64': ('llama-b11457-bin-win-cpu-x64.zip', 19436652,
                    'ed20ed40e10c04d0853d8acf8700f0e6c1bb8212f0cc70c3a0da13dcbbc1b802'),
    'macos-arm64': ('llama-b11457-bin-macos-arm64.tar.gz', 12007659,
                    'e234070cbde0c8b0d30f79fa08ff8246abe22c72acb752619349b8d9c46f7839'),
    'macos-x64': ('llama-b11457-bin-macos-x64.tar.gz', 11525345,
                  'f807f15aa0d4d9947b9befd06b3ff4bd8ddd30775d7b4b4505c8d3c5f33f0014'),
}
# A llama-server of the user's own, for platforms without a pinned build (Linux) or for testing.
SERVER_ENV = 'DUNGEON_LLAMA_SERVER'
MODELS_ENV = 'DUNGEON_EMBEDDING_MODELS'
SUGGESTED = [
    {'name': 'EmbeddingGemma 2', 'file': 'embeddinggemma-2-Q8_0.gguf', 'size_mb': 310, 'memory_mb': 350,
     'page': 'https://huggingface.co/ggml-org/embeddinggemma-2-GGUF/blob/main/embeddinggemma-2-Q8_0.gguf',
     'licence': "Apache 2.0, with Google's Gemma prohibited use policy",
     'note': 'Recommended. Small and quick; scores sit close together, but the related memory still comes first.'},
    {'name': 'Qwen3 Embedding 0.6B', 'file': 'Qwen3-Embedding-0.6B-Q8_0.gguf', 'size_mb': 640, 'memory_mb': 950,
     'page': 'https://huggingface.co/Qwen/Qwen3-Embedding-0.6B-GGUF/blob/main/Qwen3-Embedding-0.6B-Q8_0.gguf',
     'licence': 'Apache 2.0',
     'note': 'Tells related memories from unrelated ones more clearly, and needs about a gigabyte of memory.'},
]
GUARD = Path(__file__).with_name('embedding_guard.py')
CONTEXT = 2048
START_SECONDS = 120
RETRY_SECONDS = 30
POLL_SECONDS = 0.25
DOWNLOAD_SECONDS = 600
MODEL_SCAN_LIMIT = 5000


def platform_key() -> str | None:
    machine = platform.machine().lower()
    if sys.platform == 'win32' and machine in {'amd64', 'x86_64'}:
        return 'windows-x64'
    if sys.platform == 'darwin':
        return 'macos-arm64' if machine == 'arm64' else 'macos-x64'
    return None


def server_name() -> str:
    return 'llama-server.exe' if sys.platform == 'win32' else 'llama-server'


def threads() -> int:
    """Half the cores, at most four: recall is background work and the PC stays responsive."""
    return max(1, min(4, (os.cpu_count() or 2) // 2))


def read(connection) -> dict:
    row = one(connection, 'SELECT * FROM builtin_recall WHERE id=1')
    return {'enabled': bool(row['enabled']), 'model_path': row['model_path']}


def recall_config(connection) -> dict | None:
    """The settings recall uses while built-in recall is on, in the shape of a profile's."""
    current = read(connection)
    if not current['enabled'] or not current['model_path']:
        return None
    return {'provider': 'local', 'model': 'built-in', 'base_url': 'http://127.0.0.1', 'timeout_seconds': 60,
            'embedding_model': 'builtin:' + Path(current['model_path']).name, 'resource_group': 'builtin-recall',
            'builtin': True, 'credential_ref': None, 'profile_id': None, 'profile_name': 'Built-in recall'}


def model_folders(folder: Path) -> list[tuple[str, Path]]:
    home = Path.home()
    found = [('Companion', folder / 'models'), ('LM Studio', home / '.lmstudio' / 'models'),
             ('LM Studio', home / '.cache' / 'lm-studio' / 'models')]
    extra = os.environ.get(MODELS_ENV, '')
    return found + [('Your folder', Path(path)) for path in extra.split(os.pathsep) if path]


def is_embedding_file(name: str) -> bool:
    lower = name.lower()
    return lower.endswith('.gguf') and 'embed' in lower and 'mmproj' not in lower


def find_models(folder: Path) -> list[dict]:
    """Embedding model files in the Companion's models folder and LM Studio's, a few levels deep."""
    found, seen = [], 0
    for source, root in model_folders(folder):
        if not root.is_dir():
            continue
        for directory, subfolders, files in os.walk(root):
            seen += len(files) + len(subfolders)
            if seen > MODEL_SCAN_LIMIT:
                return found
            if len(Path(directory).relative_to(root).parts) >= 4:
                subfolders.clear()
            found += [{'path': str(Path(directory) / name), 'name': name, 'source': source,
                       'size_mb': round((Path(directory) / name).stat().st_size / 1e6)}
                      for name in sorted(files) if is_embedding_file(name)]
    return found


def check_model(path: str):
    require(Path(path).is_absolute(), 'Use the full path of the model file.', 422)
    require(Path(path).suffix.lower() == '.gguf', 'Choose a .gguf model file.', 422)
    require(Path(path).is_file(), 'That model file was not found.', 422)


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(('127.0.0.1', 0))
        return probe.getsockname()[1]


def command(server: str, model: str, port: int) -> list[str]:
    arguments = [server, '-m', model, '--embedding', '--host', '127.0.0.1', '--port', str(port), '-ngl', '0',
                 '-c', str(CONTEXT), '-b', str(CONTEXT), '-ub', str(CONTEXT), '-t', str(threads()), '--no-webui']
    # Qwen3 embeddings are read from the last token; other models carry their pooling in the file.
    return arguments + (['--pooling', 'last'] if 'qwen3' in Path(model).name.lower() else [])


def log_tail(path: Path, lines=6) -> str:
    """Why the server stopped: llama.cpp's own reason when it gave one, else the end of its log."""
    try:
        text = path.read_text('utf-8', errors='replace').strip().splitlines()
    except OSError:
        return ''
    reason = next((line for line in text if 'error loading model:' in line), None)
    if reason:
        return 'llama.cpp could not load the model: ' + reason.split('error loading model:', 1)[1].strip()[:500]
    return ' '.join(text[-lines:])[-600:]


class BuiltinRecall:
    """Starts, watches and stops the built-in llama.cpp server. Built-in chat (builtin_chat.py) is the same server
    with another build, model and command."""
    build = ''
    label = 'recall server'
    model_label = 'recall model'
    folder_name = 'embeddings'
    start_seconds = START_SECONDS

    def __init__(self, database, spawn=None, transport: httpx.AsyncBaseTransport | None = None):
        self.database = database
        self.folder = database.root / self.folder_name  # Shared by every world.
        self.spawn = spawn or subprocess.Popen
        self.transport = transport
        self.process = None
        self.port = None
        self.launched: tuple[str, str] | None = None
        self.task: asyncio.Task | None = None
        self.failed_at = 0.0
        self.state = 'off'
        self.message = ''
        self.downloading = False

    # --- the runtime ---------------------------------------------------------------------------

    def runtime_folder(self) -> Path:
        return self.folder / 'llama.cpp' / (RUNTIME_TAG + self.build)

    def installed_server(self) -> Path | None:
        root = self.runtime_folder()
        return next((path for path in root.rglob(server_name()) if path.is_file()), None) if root.is_dir() else None

    def server(self) -> str | None:
        own = os.environ.get(SERVER_ENV)
        if own:
            return own
        installed = self.installed_server()
        return str(installed) if installed else None

    def runtime(self) -> dict:
        key = platform_key()
        asset = self.assets().get(key)
        return {'version': RUNTIME_TAG, 'installed': self.server() is not None, 'path': self.server(),
                'available': asset is not None, 'download_mb': round(asset[1] / 1e6) if asset else None,
                'downloading': self.downloading}

    async def install(self) -> dict:
        """Download the pinned llama.cpp build for this PC, check it and unpack it."""
        asset = self.assets().get(platform_key())
        require(asset is not None, 'There is no built-in llama.cpp download for this computer. Set '
                f'{SERVER_ENV} to a llama-server you installed.', 409)
        require(not self.downloading, 'llama.cpp is already downloading.', 409)
        self.downloading = True
        try:
            archive = await self.download(*asset)
            await asyncio.to_thread(self.unpack, archive)
        finally:
            self.downloading = False
        require(self.installed_server() is not None, 'The download did not contain llama-server.', 502)
        return self.runtime()

    async def download(self, name: str, size: int, digest: str) -> Path:
        target = self.folder / 'downloads' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        hasher, received = hashlib.sha256(), 0
        try:
            async with httpx.AsyncClient(transport=self.transport, timeout=DOWNLOAD_SECONDS, follow_redirects=True,
                                         trust_env=True) as client:
                async with client.stream('GET', f'{RELEASES}/{RUNTIME_TAG}/{name}') as response:
                    require(response.status_code == 200, f'The download failed ({response.status_code}).', 502)
                    with target.open('wb') as file:
                        async for chunk in response.aiter_bytes():
                            received += len(chunk)
                            require(received <= size, 'The download is larger than expected.', 502)
                            hasher.update(chunk)
                            file.write(chunk)
        except httpx.HTTPError as error:
            raise DomainError('Cannot download llama.cpp. Check your internet connection.', 502) from error
        if received != size or hasher.hexdigest() != digest:
            target.unlink(missing_ok=True)
            raise DomainError('The llama.cpp download did not match its checksum, so it was not used.', 502)
        return target

    def unpack(self, archive: Path):
        destination = self.runtime_folder()
        staging = destination.with_name(destination.name + '.partial')
        shutil.rmtree(staging, ignore_errors=True)
        staging.mkdir(parents=True)
        if archive.name.endswith('.zip'):
            with zipfile.ZipFile(archive) as bundle:
                bundle.extractall(staging)
        else:
            with tarfile.open(archive) as bundle:
                bundle.extractall(staging, filter='data')
        shutil.rmtree(destination, ignore_errors=True)
        staging.rename(destination)
        archive.unlink(missing_ok=True)

    # --- the server ----------------------------------------------------------------------------

    def wanted(self) -> tuple[str, str] | None:
        with self.database.connect() as connection:
            current = read(connection)
        server = self.server()
        if not current['enabled'] or not current['model_path'] or not server:
            return None
        return server, current['model_path']

    def status(self) -> dict:
        return {'state': self.state, 'message': self.message}

    def kick(self) -> asyncio.Task | None:
        """Start the server for the current settings unless it is already starting or running."""
        wanted = self.wanted()
        if wanted is None:
            self.shutdown()
            self.state, self.message = 'off', ''
            return None
        if wanted == self.launched and self.task is not None:
            if not self.task.done() or (self.state == 'ready' and self.process.poll() is None):
                return self.task
            if self.state == 'failed' and time.monotonic() - self.failed_at < RETRY_SECONDS:
                return self.task
        self.shutdown()
        self.launched = wanted
        # Said now, not when the task first runs, so the answer to the request that turned it on says so.
        self.state, self.message = 'starting', ''
        self.task = asyncio.get_running_loop().create_task(self.start(*wanted))
        self.task.add_done_callback(lambda task: task.cancelled() or task.exception())
        return self.task

    async def address(self) -> str:
        """The server's API address, starting it if needed. The caller's timeout bounds the wait."""
        task = self.kick()
        require(task is not None, 'Built-in recall is off.', 409)
        await asyncio.shield(task)
        return f'http://127.0.0.1:{self.port}/v1'

    async def start(self, server: str, model: str):
        self.state, self.message = 'starting', ''
        try:
            if not Path(model).is_file():
                raise DomainError(f'The {self.model_label} file was moved or deleted.', 503)
            self.port = port = self.choose_port()
            log = self.folder / 'llama-server.log'
            log.parent.mkdir(parents=True, exist_ok=True)
            with log.open('wb') as output:
                self.process = process = self.spawn(
                    [sys.executable, '-I', str(GUARD), *self.command(server, model, port)], stdin=subprocess.PIPE,
                    stdout=output, stderr=subprocess.STDOUT, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            await self.until_ready(process, port, log)
        except DomainError as error:
            self.fail(error.message)
            raise
        except (OSError, httpx.HTTPError) as error:
            self.fail(f'The {self.label} could not start: {error}')
            raise DomainError(self.message, 503) from error
        self.state = 'ready'

    async def until_ready(self, process, port: int, log: Path):
        deadline = time.monotonic() + self.start_seconds
        async with httpx.AsyncClient(transport=self.transport, timeout=2, trust_env=False) as client:
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise DomainError(f'The {self.label} stopped while loading. ' + log_tail(log), 503)
                try:
                    response = await client.get(f'http://127.0.0.1:{port}/health')
                    if response.status_code == 200:
                        return
                except httpx.RequestError:
                    pass
                await asyncio.sleep(POLL_SECONDS)
        raise DomainError(f'The {self.label} took too long to load its model.', 503)

    def assets(self) -> dict:
        return RUNTIMES

    def choose_port(self) -> int:
        return free_port()

    def command(self, server: str, model: str, port: int) -> list[str]:
        return command(server, model, port)

    async def stop(self):
        """Stop the server from the event loop: a start still loading is cancelled first."""
        if self.task is not None and not self.task.done():
            self.task.cancel()
        await asyncio.to_thread(self.shutdown)
        self.state, self.message = 'off', ''

    def fail(self, message: str):
        self.state, self.message, self.failed_at = 'failed', message, time.monotonic()
        self.shutdown(keep_state=True)

    def shutdown(self, keep_state=False):
        """Stop the server: closing the guard's stdin stops it, and killing the guard is the fallback."""
        process, self.process = self.process, None
        if not keep_state:
            self.launched, self.task = None, None
        if process is None or process.poll() is not None:
            return
        try:
            process.stdin.close()
            process.wait(timeout=6)
        except (OSError, subprocess.TimeoutExpired):
            process.kill()
