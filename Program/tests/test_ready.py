"""Set it up for me (dungeon/ready.py): the model it picks, the confirmed download that resumes, and the built-in
chat profile it leaves (dungeon/providers/builtin_chat.py)."""
import hashlib
import time
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from dungeon import ready
from dungeon.identity import CLIENT_HEADER
from dungeon.main import create_app
from dungeon.providers import builtin_chat, builtin_recall
from dungeon.providers.chat import ChatProvider
from dungeon.providers.vault import MemoryVault
from dungeon.text_models import config_for
from tests.test_builtin_recall import Machine, runtime_zip

MODEL = b'GGUF' + bytes(range(256)) * 40


def card(name, memory, usable=None):
    return {'index': 0, 'name': name, 'memory_gb': memory, 'usable_gb': usable or memory, 'used_gb': None,
            'shared': False}


def report(gpus, images=()):
    return {'computer': {'gpus': gpus, 'memory_gb': 32.0}, 'local_images': list(images)}


def test_the_biggest_model_that_fits_whole_is_picked():
    assert ready.pick(report([card('RTX 4090', 24.0)]))[0]['key'] == 'qwen3.8-27b'
    assert ready.pick(report([card('RTX 4070', 12.0)]))[0]['key'] == 'qwen3.5-9b-q8'
    assert ready.pick(report([card('RTX 3060 Ti', 8.0)]))[0]['key'] == 'qwen3.5-9b'
    small, why = ready.pick(report([card('GTX 1650', 4.0)]))
    assert small['key'] == 'qwen3.5-4b' and 'GTX 1650' in why
    tiny, why = ready.pick(report([card('Old card', 2.0)]))
    assert tiny['key'] == 'qwen3.5-4b' and 'processor' in why
    none, why = ready.pick(report([]))
    assert none['key'] == 'qwen3.5-4b' and 'processor' in why


def test_local_pictures_on_the_same_card_keep_their_room():
    comfy = {'label': 'ComfyUI', 'size_gb': 11.0}
    chosen, why = ready.pick(report([card('RTX 4090', 24.0)], [comfy]))
    assert chosen['key'] == 'qwen3.5-9b-q8' and 'beside your local pictures' in why
    # A second card that holds the pictures leaves the big one to the chat model.
    two = report([card('RTX 5090', 32.0), {**card('RTX 4090', 24.0), 'index': 1}], [comfy])
    assert ready.pick(two)[0]['key'] == 'qwen3.8-27b'


def test_a_card_with_room_to_spare_gets_the_bigger_context():
    big, nine = ready.MODELS[0], ready.MODELS[1]
    assert ready.context_for(big, 24.0) == 32768  # 21 GB plus 1 GB more for 32K.
    assert ready.context_for(big, 21.5) == 16384
    assert ready.context_for(nine, 12.0) == 16384 and ready.context_for(nine, 12.6) == 32768
    assert ready.context_for(ready.MODELS[-1], 0.0) == 16384  # On the processor: the usual context.


def test_every_model_is_pinned_and_needs_no_click_through():
    for item in ready.MODELS:
        assert len(item['revision']) == 40 and len(item['sha256']) == 64 and item['bytes'] > 10**9
        assert ready.url(item).startswith('https://huggingface.co/unsloth/') and item['revision'] in ready.url(item)
    assert ready.LICENCE == 'Apache 2.0'


class Hub(Machine):
    """The PC plus Hugging Face: serves the model file, honours ranges, and can drop the connection once."""

    def __init__(self, archive):
        super().__init__(archive)
        self.drop_after = None
        self.ranges = []
        self.chats = []

    def handle(self, request: httpx.Request) -> httpx.Response:
        if request.url.host == 'huggingface.co':
            return self.serve(request)
        if request.url.path.endswith('/chat/completions'):
            self.chats.append(request.url.port)
            return httpx.Response(200, text='data: {"choices":[{"delta":{"content":"hey"}}]}\n\ndata: [DONE]\n\n',
                                  headers={'content-type': 'text/event-stream'})
        return super().handle(request)

    def serve(self, request):
        start = int(request.headers['range'].split('=')[1].rstrip('-')) if 'range' in request.headers else 0
        self.ranges.append(start)
        body = MODEL[start:]
        if self.drop_after is not None:
            cut, self.drop_after = self.drop_after, None
            return httpx.Response(206 if start else 200, stream=Dropping(body[:cut]))
        return httpx.Response(206 if start else 200, content=body)


class Dropping(httpx.AsyncByteStream):
    def __init__(self, data):
        self.data = data

    async def __aiter__(self):
        yield self.data
        raise httpx.ReadError('connection reset')


class FakeHardware:
    def __init__(self, gpus):
        self.gpus = gpus

    def report(self, _database, fresh=False):
        return {'computer': {'gpus': self.gpus, 'memory_gb': 32.0, 'system': 'Windows', 'cores': 16,
                             'gpu_note': None}, 'can_run': [], 'local_text': [], 'local_images': [], 'warnings': []}


@pytest.fixture
def hub(monkeypatch):
    archive = runtime_zip()
    monkeypatch.setattr(builtin_recall, 'platform_key', lambda: 'windows-x64')
    monkeypatch.setattr(builtin_chat, 'GPU_RUNTIMES', {'windows-x64': (
        'llama-gpu.zip', len(archive), hashlib.sha256(archive).hexdigest())})
    monkeypatch.setattr(builtin_recall, 'POLL_SECONDS', 0.01)
    monkeypatch.setattr(ready, 'SPARE_BYTES', 0)
    monkeypatch.setattr(ready.asyncio, 'sleep', fast_sleep)
    monkeypatch.delenv(builtin_recall.SERVER_ENV, raising=False)
    small = {**ready.MODELS[-1], 'bytes': len(MODEL), 'sha256': hashlib.sha256(MODEL).hexdigest()}
    monkeypatch.setattr(ready, 'MODELS', [*ready.MODELS[:-1], small])
    return Hub(archive)


SLEEP = ready.asyncio.sleep


async def fast_sleep(seconds):
    await SLEEP(min(seconds, 0.01))


@pytest.fixture
def client(tmp_path, clock, hub):
    transport = httpx.MockTransport(hub.handle)
    app = create_app(tmp_path / 'workspace' / 'dungeon.sqlite3', clock=clock, vault=MemoryVault(), background=False,
                     provider=ChatProvider(transport), builtin_spawn=hub.spawn, builtin_transport=transport,
                     hardware=FakeHardware([card('GTX 1650', 4.0)]))
    with TestClient(app, headers={CLIENT_HEADER: 'workspace'}) as test_client:
        yield test_client


def settled(client, seconds=10):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        view = client.get('/api/ready').json()
        if view['status'] not in ('downloading', 'checking'):
            return view
        time.sleep(0.02)
    raise AssertionError('the download kept running')


def test_nothing_downloads_until_the_user_confirms(client, hub):
    view = client.get('/api/ready').json()
    assert view['status'] == 'idle' and view['pick']['key'] == 'qwen3.5-4b'
    assert view['pick']['bytes'] == len(MODEL) and view['pick']['quant'] == 'Q4_K_M' and view['pick']['fits']
    assert view['runtime']['installed'] is False and hub.ranges == []
    assert client.post('/api/ready', json={'model': 'gpt-9'}).status_code == 422


def test_set_it_up_downloads_resumes_and_makes_the_chat_profile(client, hub):
    hub.drop_after = 1000
    assert client.post('/api/ready', json={'model': 'qwen3.5-4b'}).json()['status'] == 'downloading'
    view = settled(client)
    assert view['status'] == 'ready', view['message']
    assert hub.ranges == [0, 1000]  # The dropped download carried on from where it stopped.
    assert view['received'] == view['total'] == len(MODEL) and view['runtime']['installed']
    with client.app.state.database.connect() as connection:
        config = config_for(connection, 'chat')
    assert config['profile_name'] == 'Built-in · Qwen3.5 4B' and config['resource_group'] == 'builtin-chat'
    assert config['model'] == 'Qwen3.5-4B-Q4_K_M' and config['provider'] == 'local'
    # Qwen's non-thinking sampling, and a 4 GB card has no room for more than the usual context.
    assert (config['temperature'], config['top_p'], config['top_k'], config['min_p'], config['presence_penalty'],
            config['repetition_penalty']) == (0.7, 0.8, 20, 0.0, 1.5, 1.0)
    assert config['context_tokens'] == 16384
    arguments = hub.processes[-1].arguments
    assert '--jinja' in arguments and arguments[arguments.index('-ngl') + 1] == '999'
    assert arguments[arguments.index('-c') + 1] == '16384'
    assert arguments[arguments.index('--reasoning-budget') + 1] == '0'
    for flag, value in [('--temp', '0.7'), ('--top-p', '0.8'), ('--top-k', '20'), ('--min-p', '0.0'),
                        ('--presence-penalty', '1.5'), ('--repeat-penalty', '1.0')]:
        assert arguments[arguments.index(flag) + 1] == value


def test_a_bad_download_is_thrown_away(client, hub, monkeypatch):
    broken = {**ready.MODELS[-1], 'sha256': '0' * 64}
    monkeypatch.setattr(ready, 'MODELS', [*ready.MODELS[:-1], broken])
    client.post('/api/ready', json={'model': 'qwen3.5-4b'})
    view = settled(client)
    assert view['status'] == 'failed' and 'damaged' in view['message'] and view['received'] == 0
    assert not list((client.app.state.builtin_chat.folder / 'models').glob('*.partial'))


def test_not_enough_disk_space_says_so(client, monkeypatch):
    monkeypatch.setattr(ready.Ready, 'free_bytes', lambda self: 10)
    response = client.post('/api/ready', json={'model': 'qwen3.5-4b'})
    assert response.status_code == 409 and 'disk space' in response.json()['detail']


def test_cancel_keeps_the_part_for_undo_then_clears_it(client, monkeypatch):
    async def stalls(self, item, partial, have):
        partial.write_bytes(MODEL[:1000])
        self.received = 1000
        await ready.asyncio.Event().wait()

    monkeypatch.setattr(ready.Ready, 'receive', stalls)
    client.post('/api/ready', json={'model': 'qwen3.5-4b'})
    deadline = time.monotonic() + 5
    while client.get('/api/ready').json()['received'] < 1000 and time.monotonic() < deadline:
        time.sleep(0.02)
    view = client.post('/api/ready/cancel').json()
    assert view['status'] == 'cancelled' and view['received'] == 1000
    assert client.post('/api/ready', json={'model': 'qwen3.5-4b'}).json()['status'] == 'downloading'  # Undo
    client.post('/api/ready/cancel')
    view = client.delete('/api/ready').json()
    assert view['status'] == 'idle' and view['received'] == 0
    assert not list((client.app.state.builtin_chat.folder / 'models').glob('*.partial'))


def test_a_chat_profile_picked_during_the_download_stays(client, hub, monkeypatch):
    real = ready.Ready.make_profile

    def picked_meanwhile(self, item, port, context):
        with client.app.state.database.connect(write=True) as connection:
            connection.execute("INSERT INTO model_profiles (id, name, config, revision, created_at, updated_at) "
                               "VALUES ('theirs', 'Theirs', '{}', 1, 'now', 'now')")
            connection.execute("INSERT OR REPLACE INTO model_routes (job, profile_id, updated_at) "
                               "VALUES ('chat', 'theirs', 'now')")
        real(self, item, port, context)

    monkeypatch.setattr(ready.Ready, 'make_profile', picked_meanwhile)
    client.post('/api/ready', json={'model': 'qwen3.5-4b'})
    view = settled(client)
    assert view['status'] == 'ready' and view['in_use'] is False and view['profile_id']
    assert not hub.processes  # Not loaded onto the card beside their own model until they choose it.
    assert client.post('/api/ready/use').json()['in_use'] is True


def test_a_check_cut_short_by_a_restart_runs_again(client, hub):
    client.post('/api/ready', json={'model': 'qwen3.5-4b'})
    assert settled(client)['status'] == 'ready'
    ready_app = client.app.state.ready
    path = ready_app.target(ready.model('qwen3.5-4b'))
    path.replace(path.with_name(path.name + '.partial'))
    ready_app.save(status='checking')

    async def restart():
        ready_app.recover()

    client.portal.call(restart)
    assert settled(client)['status'] == 'ready'


def test_the_view_names_the_card_the_drive_and_the_runtime_download(client):
    view = client.get('/api/ready').json()
    assert view['card'] == {'name': 'GTX 1650', 'memory_gb': 4.0}
    assert view['runtime_bytes'] > 0 and view['drive'] and view['seconds_left'] is None
    assert client.post('/api/ready/seen', json={'what': 'notice'}).json()['announced'] is True


def test_saving_the_setup_waits_out_a_reader_that_has_it_open(tmp_path, monkeypatch):
    from dungeon.providers import builtin_chat
    real, turned_away = Path.replace, []

    def busy_once(self, target):
        if not turned_away:
            turned_away.append(target)
            raise PermissionError(5, 'Access is denied')
        return real(self, target)

    monkeypatch.setattr(Path, 'replace', busy_once)
    builtin_chat.write_state(tmp_path, {'status': 'ready'})
    assert turned_away and builtin_chat.read_state(tmp_path) == {'status': 'ready'}
    assert not list((tmp_path / 'chat').glob('*.partial'))
