"""Ready on first launch: "Set it up for me" picks a chat model that fits this computer, downloads it and makes it the
model companions reply with (Hit List #27).

The app decides which model, from what the graphics card can hold (dungeon/hardware.py) less the room local
pictures need on the same card; the user may pick another from the same short list. Nothing downloads until the user
presses the button and confirms the model, its quantization and the download size (Vanta, 2026-10-12): a 3 to 18 GB
download is the one decision the app does not make for them. Once confirmed it runs in the background while they make
their first companion, carries on where it stopped after a dropped connection or a restart (HTTP ranges), and is
checked against its SHA-256 before it is used. Then a "Built-in" chat profile is made and given the chat job, and the
model runs through llama.cpp's server (dungeon/providers/builtin_chat.py).

Only models whose licence asks for no click-through are offered (Apache 2.0, from unsloth's GGUF builds pinned to one
commit), so the download needs no account. Gemma and Llama models stay links in Settings > Models.
"""
import asyncio
import errno
import hashlib
import logging
import shutil
import time
from pathlib import Path

import httpx

from dungeon import hardware
from dungeon.database import decode, encode, identifier, many
from dungeon.errors import DomainError, require
from dungeon.providers.builtin_chat import CONTEXT, RESOURCE_GROUP, ROOMY_CONTEXT, SAMPLING, read_state, write_state
from dungeon.providers.builtin_recall import free_port
from dungeon.providers.config import SavedProfileConfig
from dungeon.text_models import CHAT, assign, assigned, routes

log = logging.getLogger('dungeon')
HUB = 'https://huggingface.co'
# Biggest first; `needs_gb` is the file plus a 16K context's memory, so the whole model stays on the card.
# Sizes and SHA-256 from the Hugging Face API on 2026-10-12, at the commit in `revision`. `kv_bytes` is the
# context's memory per token at 16 bits, from each model's config.json: 2 (keys and values) x full-attention layers
# (one in four: 8 of 32, or 16 of 64 for the 27B) x 4 key-value heads x 256 per head x 2 bytes. The other layers
# keep a state of fixed size.
MODELS = [
    {'key': 'qwen3.8-27b', 'name': 'Qwen3.8 27B', 'quant': 'Q4_K_XL', 'bits': '4-bit', 'needs_gb': 21.0,
     'kv_bytes': 65536, 'repo': 'unsloth/Qwen3.8-27B-GGUF',
     'revision': '4ca720788d1e01f1bff70c033e0d0028fd02e502',
     'file': 'Qwen3.8-27B-UD-Q4_K_XL.gguf', 'bytes': 17559178144,
     'sha256': '3f227079003add2511437e5b1e94812e363385225bf6a9b47b0054a72bc8b01e'},
    {'key': 'qwen3.5-9b-q8', 'name': 'Qwen3.5 9B', 'quant': 'Q8_0', 'bits': '8-bit', 'needs_gb': 12.0,
     'kv_bytes': 32768, 'repo': 'unsloth/Qwen3.5-9B-GGUF',
     'revision': '3885219b6810b007914f3a7950a8d1b469d598a5',
     'file': 'Qwen3.5-9B-Q8_0.gguf', 'bytes': 9527502048,
     'sha256': '809626574d0cb43d4becfa56169980da2bb448f2299270f7be443cb89d0a6ae4'},
    {'key': 'qwen3.5-9b', 'name': 'Qwen3.5 9B', 'quant': 'Q4_K_M', 'bits': '4-bit', 'needs_gb': 7.0,
     'kv_bytes': 32768, 'repo': 'unsloth/Qwen3.5-9B-GGUF',
     'revision': '3885219b6810b007914f3a7950a8d1b469d598a5',
     'file': 'Qwen3.5-9B-Q4_K_M.gguf', 'bytes': 5680522464,
     'sha256': '03b74727a860a56338e042c4420bb3f04b2fec5734175f4cb9fa853daf52b7e8'},
    {'key': 'qwen3.5-4b', 'name': 'Qwen3.5 4B', 'quant': 'Q4_K_M', 'bits': '4-bit', 'needs_gb': 4.0,
     'kv_bytes': 32768, 'repo': 'unsloth/Qwen3.5-4B-GGUF',
     'revision': 'e87f176479d0855a907a41277aca2f8ee7a09523',
     'file': 'Qwen3.5-4B-Q4_K_M.gguf', 'bytes': 2740937888,
     'sha256': '00fe7986ff5f6b463e62455821146049db6f9313603938a70800d1fb69ef11a4'},
]
LICENCE = 'Apache 2.0'
ATTEMPTS = 12
CHUNK = 1 << 20
SAVE_EVERY = 64 * CHUNK
SPARE_BYTES = 2 * 10**9
TIMEOUT = httpx.Timeout(60, connect=20)
# Time left is shown once this much of the download has been timed, so it never flickers (Iris).
RATE_AFTER_SECONDS = 10
# Steps where the download is under way or waiting on the user, so a new press resumes rather than starts over.
UNDER_WAY = ('downloading', 'checking', 'paused', 'cancelled', 'failed')


def uses_builtin(database) -> bool:
    """Whether the built-in chat model does the chat job in this world, so it is worth loading at startup."""
    with database.connect() as connection:
        row = assigned(connection, CHAT)
    return row is not None and decode(row['config']).get('resource_group') == RESOURCE_GROUP


def builtin_profiles(database) -> list[str]:
    """The chat profiles that run on the built-in server."""
    with database.connect() as connection:
        return [row['id'] for row in many(connection, 'SELECT id, config FROM model_profiles')
                if decode(row['config']).get('resource_group') == RESOURCE_GROUP]


def model(key: str) -> dict:
    found = next((item for item in MODELS if item['key'] == key), None)
    require(found is not None, 'That model is not one the Dungeon can set up.', 422)
    return found


def room(report: dict) -> tuple[float, str]:
    """Memory the chat model may use on the biggest card, and why, after local pictures take their share of it."""
    gpus = sorted(report['computer']['gpus'], key=lambda gpu: gpu['usable_gb'], reverse=True)
    if not gpus:
        return 0.0, 'No graphics card was measured, so the model runs on the processor and replies come slowly.'
    best, images = gpus[0], report.get('local_images') or []
    picture = max((image['size_gb'] for image in images), default=0.0)
    elsewhere = any(gpu['usable_gb'] >= picture for gpu in gpus[1:])
    if picture and not elsewhere:
        return max(best['usable_gb'] - picture, 0.0), (f"It fits on the {best['name']} beside your local pictures "
                                                       f"(about {hardware.gb(picture)}).")
    return best['usable_gb'], f"It fits on the {best['name']} ({hardware.gb(best['memory_gb'])})."


def pick(report: dict) -> tuple[dict, str]:
    """The biggest model that fits whole, else the smallest, which then runs partly on the processor."""
    space, reason = room(report)
    fitting = next((item for item in MODELS if item['needs_gb'] <= space), None)
    if fitting:
        return fitting, reason
    if space or reason.startswith('It fits'):  # Local pictures can leave no room at all: nothing fits then.
        reason = 'Your graphics card is small for a chat model, so part of it runs on the processor and replies ' \
                 'come slowly.'
    return MODELS[-1], reason


def context_for(item: dict, space: float) -> int:
    """The context the model runs with: twice the usual when the card holds the extra memory too (0.5 GB, or 1 GB for
    the 27B), so more of the chat and its memories fit; the usual 16K otherwise."""
    extra = (ROOMY_CONTEXT - CONTEXT) * item['kv_bytes'] / 1e9
    return ROOMY_CONTEXT if space >= item['needs_gb'] + extra else CONTEXT


def card(report: dict) -> dict | None:
    """The card the chat model runs on: the biggest one."""
    gpus = sorted(report['computer']['gpus'], key=lambda gpu: gpu['usable_gb'], reverse=True)
    return {'name': gpus[0]['name'], 'memory_gb': gpus[0]['memory_gb']} if gpus else None


def drive(path: Path) -> str:
    """The drive the model goes on, as people know it: "Z:" on Windows, else "this drive"."""
    anchor = path.resolve().drive
    return anchor or 'this drive'


def chat_profile(connection) -> str | None:
    return routes(connection).get(CHAT)


def page(item: dict) -> str:
    return f"{HUB}/{item['repo']}"


def url(item: dict) -> str:
    return f"{HUB}/{item['repo']}/resolve/{item['revision']}/{item['file']}"


def listed(item: dict, space: float) -> dict:
    keep = ('key', 'name', 'quant', 'bits', 'bytes', 'file')
    return {**{key: item[key] for key in keep}, 'licence': LICENCE, 'page': page(item),
            'fits': item['needs_gb'] <= space}


def sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open('rb') as file:
        while block := file.read(16 * CHUNK):
            hasher.update(block)
    return hasher.hexdigest()


class Ready:
    """The "Set it up for me" download and the built-in chat profile it leaves behind."""

    def __init__(self, database, chat, hardware_report, transport: httpx.AsyncBaseTransport | None = None):
        self.database = database
        self.chat = chat
        self.report = hardware_report
        self.transport = transport
        self.task: asyncio.Task | None = None
        self.received = 0
        self.waiting = False
        self.timed: tuple[float, int] | None = None  # When this stretch of the download began, and from which byte.

    @property
    def folder(self) -> Path:
        return self.chat.folder / 'models'

    def state(self) -> dict:
        return read_state(self.database.root)

    def save(self, **changes) -> dict:
        state = {**self.state(), **changes}
        write_state(self.database.root, state)
        return state

    def view(self) -> dict:
        report = self.report()
        space, _ = room(report)
        chosen, reason = pick(report)
        state = self.state()
        runtime = self.chat.runtime()
        received = self.received if self.running() else state.get('received', 0)
        return {'pick': listed(chosen, space), 'reason': reason, 'models': [listed(item, space) for item in MODELS],
                'runtime': runtime, 'runtime_bytes': self.runtime_bytes(runtime), 'card': card(report),
                'status': state.get('status', 'idle'), 'model': state.get('model_key'),
                'received': received, 'total': state.get('bytes', 0), 'message': state.get('message', ''),
                'waiting': self.waiting and self.running(), 'seconds_left': self.seconds_left(received, state),
                'server': self.chat.status(), 'free_bytes': self.free_bytes(), 'drive': drive(self.chat.folder),
                'in_use': state.get('status') == 'ready' and uses_builtin(self.database),
                'profile_id': state.get('profile_id'), 'announced': bool(state.get('announced')),
                'settings_seen': bool(state.get('settings_seen'))}

    def runtime_bytes(self, runtime: dict) -> int:
        """The llama.cpp download that comes first, when this computer doesn't have it yet."""
        asset = None if runtime.get('installed') else self.chat.assets().get(self.platform())
        return asset[1] if asset else 0

    def seconds_left(self, received: int, state: dict) -> int | None:
        if not self.running() or self.waiting or self.timed is None:
            return None
        began, start = self.timed
        elapsed = time.monotonic() - began
        if elapsed < RATE_AFTER_SECONDS or received <= start:
            return None
        return round((state.get('bytes', 0) - received) / ((received - start) / elapsed))

    def free_bytes(self) -> int | None:
        try:
            return shutil.disk_usage(self.chat.folder if self.chat.folder.exists() else self.database.root).free
        except OSError:
            return None

    def running(self) -> bool:
        return self.task is not None and not self.task.done()

    def start(self, key: str) -> dict:
        """Begin (or carry on with) the confirmed download in the background."""
        item = model(key)
        require(not self.running(), 'The chat model is already downloading.', 409)
        require(self.chat.assets().get(self.platform()) is not None or self.chat.server() is not None,
                'There is no built-in llama.cpp for this computer yet, so the Dungeon cannot run a chat model '
                'itself. Set up LM Studio or a hosted service in Settings > Models.', 409)
        partial = self.target(item).with_name(item['file'] + '.partial')
        have = item['bytes'] if self.kept(item) else partial.stat().st_size if partial.exists() else 0
        free = self.free_bytes()
        require(free is None or free >= item['bytes'] - have + SPARE_BYTES,
                f"There is not enough free disk space for {item['name']}: it needs about "
                f"{(item['bytes'] - have + SPARE_BYTES) / 1e9:.1f} GB free.", 409)
        if self.state().get('status') not in UNDER_WAY:
            # The chat profile in use as it starts: if the user picks another meanwhile, theirs stays (Iris).
            with self.database.connect() as connection:
                self.save(chat_before=chat_profile(connection), announced=False, settings_seen=False)
        self.save(status='downloading', model_key=key, bytes=item['bytes'], received=have, message='')
        self.launch(item)
        return self.view()

    def platform(self) -> str | None:
        from dungeon.providers.builtin_recall import platform_key
        return platform_key()

    def launch(self, item: dict):
        self.received = self.state().get('received', 0)
        self.task = asyncio.get_running_loop().create_task(self.run(item))
        self.task.add_done_callback(lambda task: task.cancelled() or task.exception())

    def recover(self):
        """After a restart, a download the user confirmed carries on where it stopped, and one they cancelled is
        cleared away (the Undo it offered is over)."""
        state = self.state()
        if state.get('status') in ('downloading', 'checking') and state.get('model_key'):
            # A check cut short by a restart runs again: the whole part file is still there, so only the hash reruns.
            self.launch(model(state['model_key']))
        elif state.get('status') == 'cancelled':
            self.discard()

    async def stop(self):
        if self.running():
            self.task.cancel()
            try:
                await self.task
            except (asyncio.CancelledError, DomainError):
                pass

    async def pause(self) -> dict:
        await self.stop()
        if self.state().get('status') in ('downloading', 'checking'):
            self.save(status='paused', received=self.received)
        return self.view()

    async def cancel(self) -> dict:
        """Stops at once; the part already downloaded stays for the Undo the page offers, until `discard`."""
        await self.stop()
        if self.state().get('status') in ('downloading', 'checking', 'paused', 'failed'):
            self.save(status='cancelled', received=self.received or self.state().get('received', 0))
        return self.view()

    def discard(self) -> dict:
        """Deletes a cancelled download's part file."""
        state = self.state()
        if state.get('status') == 'cancelled' and state.get('model_key'):
            item = model(state['model_key'])
            self.target(item).with_name(item['file'] + '.partial').unlink(missing_ok=True)
            self.save(status='idle', model_key=None, received=0, bytes=0, message='')
        return self.view()

    def kept(self, item: dict) -> bool:
        """Whether this model's file is still here, whole and already checked, from a built-in profile since
        deleted: setting it up again needs no download."""
        path = self.target(item)
        return self.state().get('kept_key') == item['key'] and path.is_file() and path.stat().st_size == item['bytes']

    async def forget(self) -> dict:
        """After a profile is deleted: with no built-in profile left, its server stops and "Set it up for me" is
        offered again. The checked model file stays, so setting it up again is instant; the profile is the only way
        the app knows the user wants it, and a 3 to 18 GB file is a large thing to remove without being asked."""
        state = self.state()
        if state.get('status') != 'ready' or builtin_profiles(self.database):
            return self.view()
        await self.chat.stop()
        self.save(status='idle', kept_key=state.get('model_key'), model_key=None, profile_id=None, received=0,
                  bytes=0, message='', announced=False, settings_seen=False)
        return self.view()

    def use(self) -> dict:
        """The card's "Ready. Use it for the story": the built-in model takes the chat job after all."""
        profile_id = self.state().get('profile_id')
        require(self.state().get('status') == 'ready' and profile_id, 'The built-in model is not ready yet.', 409)
        with self.database.connect(write=True) as connection:
            assign(connection, CHAT, profile_id, self.database.now())
        self.chat.kick()
        return self.view()

    def seen(self, what: str) -> dict:
        self.save(**{'announced' if what == 'notice' else 'settings_seen': True})
        return self.view()

    def target(self, item: dict) -> Path:
        return self.folder / item['file']

    async def run(self, item: dict):
        try:
            if self.chat.server() is None:
                await self.chat.install()
            path = self.target(item) if self.kept(item) else await self.obtain(item)
            port = self.state().get('port') or free_port()
            context = context_for(item, room(self.report())[0])
            self.save(model_path=str(path), port=port, context=context, received=item['bytes'], message='')
            self.make_profile(item, port, context)
            self.save(status='ready')  # Ready once its profile is there, so "ready" never shows without one.
            if uses_builtin(self.database):  # Picked another chat model meanwhile: it loads only when they Use it.
                self.chat.kick()
        except DomainError as error:
            self.save(status='failed', message=error.message, received=self.received)
            return
        except asyncio.CancelledError:
            raise
        except (OSError, httpx.HTTPError) as error:
            log.warning('Set it up for me failed: %s', error)
            self.save(status='failed', message=self.stopped(error), received=self.received)

    async def obtain(self, item: dict) -> Path:
        """The model file, downloaded and checked against its SHA-256."""
        path = await self.fetch(item)
        self.save(status='checking', received=item['bytes'])
        digest = await asyncio.to_thread(sha256, path.with_name(path.name + '.partial'))
        if digest != item['sha256']:
            path.with_name(path.name + '.partial').unlink(missing_ok=True)
            self.received = 0
            # The file's checksum didn't match: said plainly (Iris).
            raise DomainError('The download came through damaged, so it wasn\'t used. Try again to download it '
                              'fresh.', 502)
        path.with_name(path.name + '.partial').replace(path)
        return path

    def stopped(self, error: Exception) -> str:
        if isinstance(error, OSError) and error.errno == errno.ENOSPC:
            return (f'Stopped: {drive(self.chat.folder)} is full at {self.received / 1e9:.1f} GB. Free some space, '
                    'then Resume.')
        return f'The download stopped: {error}'

    async def fetch(self, item: dict) -> Path:
        """The model file, downloaded into `<file>.partial` and resumed with a range request after each drop."""
        path = self.target(item)
        partial = path.with_name(item['file'] + '.partial')
        partial.parent.mkdir(parents=True, exist_ok=True)
        failure = None
        for attempt in range(ATTEMPTS):
            have = partial.stat().st_size if partial.exists() else 0
            if have > item['bytes']:
                partial.unlink()
                have = 0
            if have == item['bytes']:
                return path
            try:
                self.timed = (time.monotonic(), have)
                await self.receive(item, partial, have)
                failure = None
            except httpx.HTTPError as error:
                failure = error
                self.waiting = True  # "Waiting for the connection…" until bytes arrive again.
                await asyncio.sleep(min(2 ** attempt, 30))
        if failure is not None or partial.stat().st_size != item['bytes']:
            raise DomainError('The download kept stopping. Check your internet connection, then press Resume.', 502)
        return path

    async def receive(self, item: dict, partial: Path, have: int):
        headers = {'Range': f'bytes={have}-'} if have else {}
        async with httpx.AsyncClient(transport=self.transport, timeout=TIMEOUT, follow_redirects=True,
                                     trust_env=True) as client:
            async with client.stream('GET', url(item), headers=headers) as response:
                if response.status_code == 200:
                    have = 0  # The server sent the whole file, not the rest of it.
                elif response.status_code != 206:
                    raise DomainError(f"The download failed ({response.status_code}).", 502)
                unsaved = 0
                with partial.open('r+b' if have else 'wb') as file:
                    file.seek(have)
                    file.truncate()
                    self.received = have
                    async for chunk in response.aiter_bytes():  # As it arrives, so a drop loses nothing.
                        self.waiting = False
                        file.write(chunk)
                        self.received += len(chunk)
                        unsaved += len(chunk)
                        require(self.received <= item['bytes'], 'The download is larger than expected.', 502)
                        if unsaved >= SAVE_EVERY:
                            self.save(received=self.received)
                            unsaved = 0

    def make_profile(self, item: dict, port: int, context: int):
        """A "Built-in" chat profile for the model, given the chat job: the user asked for this model to reply. If they
        picked another chat profile during the download, theirs stays and Settings offers this one instead. It carries
        the server's context and the models' recommended sampling, so Settings > Models shows what replies use."""
        config = SavedProfileConfig(provider='local', model=Path(item['file']).stem,
                                    base_url=f'http://127.0.0.1:{port}/v1', context_tokens=context,
                                    timeout_seconds=300, resource_group=RESOURCE_GROUP, **SAMPLING).model_dump()
        name = f"Built-in · {item['name']}"
        with self.database.connect(write=True) as connection:
            timestamp = self.database.now()
            rows = [row for row in many(connection, 'SELECT id, config FROM model_profiles')
                    if decode(row['config']).get('resource_group') == RESOURCE_GROUP]
            if rows:
                profile_id = rows[0]['id']
                connection.execute('UPDATE model_profiles SET name=?, config=?, revision=revision+1, updated_at=? '
                                   'WHERE id=?', (name, encode(config), timestamp, profile_id))
            else:
                profile_id = identifier()
                connection.execute('INSERT INTO model_profiles (id, name, config, credential_ref, revision, '
                                   'created_at, updated_at) VALUES (?, ?, ?, NULL, 1, ?, ?)',
                                   (profile_id, name, encode(config), timestamp, timestamp))
            if chat_profile(connection) == self.state().get('chat_before'):
                assign(connection, CHAT, profile_id, timestamp)
        self.save(profile_id=profile_id)
