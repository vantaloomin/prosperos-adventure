"""Built-in recall: the llama.cpp runtime download, the guarded server and the recall test (PRD M10)."""
import hashlib
import io
import json
import os
import subprocess
import sys
import time
import zipfile

import httpx
import pytest
from fastapi.testclient import TestClient

from dungeon.identity import CLIENT_HEADER
from dungeon.main import create_app
from dungeon.providers import builtin_recall
from dungeon.providers.embeddings import EmbeddingProvider, as_documents, as_query, vector_model
from dungeon.providers.vault import MemoryVault
from dungeon.text_models import config_for

GEMMA = {'embedding_model': 'builtin:embeddinggemma-2-Q8_0.gguf'}


def runtime_zip() -> bytes:
    data = io.BytesIO()
    with zipfile.ZipFile(data, 'w') as bundle:
        bundle.writestr(builtin_recall.server_name(), 'not really a server')
        bundle.writestr('ggml.dll', 'library')
    return data.getvalue()


class FakeProcess:
    def __init__(self, arguments, **_options):
        self.arguments = arguments
        self.returncode = None
        self.stdin = self
        self.closed = False

    def poll(self):
        return self.returncode

    def close(self):
        self.closed = True
        self.returncode = 0

    def wait(self, timeout=None):
        return self.returncode

    def kill(self):
        self.returncode = -9


class Machine:
    """The PC as the built-in server sees it: GitHub, the guard process and llama-server's API."""

    def __init__(self, archive: bytes):
        self.archive = archive
        self.processes = []
        self.embedded = []
        self.healthy = True
        self.crash_on_start = False

    def spawn(self, arguments, **options):
        process = FakeProcess(arguments, **options)
        if self.crash_on_start:
            process.returncode = 1
        self.processes.append(process)
        return process

    def handle(self, request: httpx.Request) -> httpx.Response:
        if request.url.host == 'github.com':
            return httpx.Response(200, content=self.archive)
        if request.url.path == '/health':
            return httpx.Response(200 if self.healthy else 503, json={})
        texts = json.loads(request.content)['input']
        self.embedded.append((request.url.port, texts))
        vectors = [[1.0 if 'sister' in text or 'Lena' in text else 0.1, 0.5] for text in texts]
        return httpx.Response(200, json={'data': [{'index': i, 'embedding': v} for i, v in enumerate(vectors)]})


@pytest.fixture
def machine(monkeypatch):
    archive = runtime_zip()
    monkeypatch.setattr(builtin_recall, 'platform_key', lambda: 'windows-x64')
    monkeypatch.setattr(builtin_recall, 'RUNTIMES', {'windows-x64': (
        'llama-test.zip', len(archive), hashlib.sha256(archive).hexdigest())})
    monkeypatch.setattr(builtin_recall, 'POLL_SECONDS', 0.01)
    monkeypatch.delenv(builtin_recall.SERVER_ENV, raising=False)
    return Machine(archive)


@pytest.fixture
def client(tmp_path, clock, provider, machine):
    transport = httpx.MockTransport(machine.handle)
    app = create_app(tmp_path / 'workspace' / 'dungeon.sqlite3', clock=clock, vault=MemoryVault(),
                     provider=provider, background=False, embedder=EmbeddingProvider(transport),
                     builtin_spawn=machine.spawn, builtin_transport=transport)
    with TestClient(app, headers={CLIENT_HEADER: 'workspace'}) as test_client:
        yield test_client


@pytest.fixture
def model_file(tmp_path):
    path = tmp_path / 'downloads' / 'embeddinggemma-2-Q8_0.gguf'
    path.parent.mkdir()
    path.write_bytes(b'GGUF')
    return path


def turn_on(client, model_file):
    assert client.post('/api/models/builtin-recall/runtime').status_code == 200
    response = client.put('/api/models/builtin-recall', json={'enabled': True, 'model_path': str(model_file)})
    assert response.status_code == 200, response.text
    return response.json()


def test_known_models_get_their_retrieval_instructions_and_their_own_vectors():
    assert as_query(GEMMA, 'hi') == 'task: search result | query: hi'
    assert as_documents(GEMMA, ['a']) == ['title: none | text: a']
    assert vector_model(GEMMA) == 'builtin:embeddinggemma-2-Q8_0.gguf#prompted-1'
    plain = {'embedding_model': 'embed-small'}
    assert as_query(plain, 'hi') == 'hi' and vector_model(plain) == 'embed-small'


def test_runtime_download_is_checked_and_unpacked(client):
    view = client.get('/api/models/builtin-recall').json()
    assert view['runtime']['installed'] is False and view['runtime']['available'] is True
    view = client.post('/api/models/builtin-recall/runtime').json()
    assert view['runtime']['installed'] is True
    assert view['runtime']['path'].endswith(builtin_recall.server_name())


def test_a_download_that_does_not_match_its_checksum_is_thrown_away(client, machine):
    machine.archive = runtime_zip() + b'tampered'
    response = client.post('/api/models/builtin-recall/runtime')
    assert response.status_code == 502
    assert client.get('/api/models/builtin-recall').json()['runtime']['installed'] is False


def test_turning_on_needs_the_runtime_and_a_model_file(client, model_file):
    response = client.put('/api/models/builtin-recall', json={'enabled': True, 'model_path': str(model_file)})
    assert response.status_code == 409 and 'llama.cpp' in response.json()['detail']
    client.post('/api/models/builtin-recall/runtime')
    missing = str(model_file.with_name('nowhere-embed.gguf'))
    response = client.put('/api/models/builtin-recall', json={'enabled': True, 'model_path': missing})
    assert response.status_code == 422


def test_built_in_recall_starts_a_guarded_cpu_server_and_passes_the_recall_test(client, machine, model_file):
    # The answer to turning it on already says it is loading, so the page keeps checking until it runs.
    assert turn_on(client, model_file)['state'] == 'starting'
    result = client.post('/api/models/recall-test').json()
    assert result['found_related'] is True and result['dimensions'] == 2
    [process] = machine.processes
    guard, server = process.arguments[2], process.arguments[3:]
    assert guard.endswith('embedding_guard.py')
    assert server[server.index('-m') + 1] == str(model_file)
    assert {'--embedding', '--no-webui'} <= set(server) and server[server.index('-ngl') + 1] == '0'
    port, texts = machine.embedded[0]
    assert port == int(server[server.index('--port') + 1])
    assert texts[0].startswith('task: search result | query: ')
    assert client.get('/api/models/builtin-recall').json()['state'] == 'ready'
    with client.app.state.database.connect() as connection:
        assert config_for(connection, 'recall')['profile_name'] == 'Built-in recall'


def test_turning_off_stops_the_server_and_recall_goes_back_to_profiles(client, machine, model_file):
    turn_on(client, model_file)
    client.post('/api/models/recall-test')
    response = client.put('/api/models/builtin-recall', json={'enabled': False, 'model_path': str(model_file)})
    assert response.json()['state'] == 'off'
    assert machine.processes[0].closed is True
    assert client.post('/api/models/recall-test').status_code == 409


def test_a_server_that_stops_while_loading_is_reported(client, machine, model_file):
    machine.crash_on_start = True
    turn_on(client, model_file)
    response = client.post('/api/models/recall-test')
    assert response.status_code == 503
    view = client.get('/api/models/builtin-recall').json()
    assert view['state'] == 'failed' and 'stopped while loading' in view['message']


def test_the_settings_list_embedding_files_but_not_vision_parts(client, tmp_path, monkeypatch):
    folder = tmp_path / 'my-models' / 'ggml-org'
    folder.mkdir(parents=True)
    for name in ('embeddinggemma-2-Q8_0.gguf', 'mmproj-embeddinggemma-2.gguf', 'llama-3-8b.gguf'):
        (folder / name).write_bytes(b'GGUF')
    monkeypatch.setenv(builtin_recall.MODELS_ENV, str(tmp_path / 'my-models'))
    found = client.get('/api/models/builtin-recall').json()['models']
    assert [model['name'] for model in found] == ['embeddinggemma-2-Q8_0.gguf']


def test_the_guard_stops_the_server_when_the_companion_goes_away(tmp_path):
    beat = tmp_path / 'beat'
    server = [sys.executable, '-c', f'import time, pathlib\nwhile True:\n pathlib.Path({str(beat)!r}).touch()\n'
              ' time.sleep(0.05)']
    guard = subprocess.Popen([sys.executable, '-I', str(builtin_recall.GUARD), *server], stdin=subprocess.PIPE)
    deadline = time.monotonic() + 10
    while not beat.exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    assert beat.exists()
    guard.stdin.close()
    assert guard.wait(timeout=10) is not None
    time.sleep(0.3)
    stopped = beat.stat().st_mtime
    time.sleep(0.5)
    assert beat.stat().st_mtime == stopped


REAL_MODEL = 'DUNGEON_TEST_EMBEDDING_MODEL'


@pytest.mark.skipif(not (os.environ.get(builtin_recall.SERVER_ENV)
                         and os.environ.get(REAL_MODEL)),
                    reason=f'set {builtin_recall.SERVER_ENV} and {REAL_MODEL} to try a real llama-server')


def test_a_model_llama_cpp_cannot_load_names_llama_cpp_reason(tmp_path):
    log = tmp_path / 'llama-server.log'
    log.write_text("I srv load_model: loading model 'x.gguf'\n"
                   "E llama_model_load: error loading model: unknown model architecture: 'gemma-embedding2'\n"
                   'E srv llama_server: exiting due to model loading error\n', encoding='utf-8')
    assert builtin_recall.log_tail(log) == "llama.cpp could not load the model: unknown model architecture: 'gemma-embedding2'"


def test_the_guard_exits_cleanly_when_the_server_stops_on_its_own(tmp_path):
    server = [sys.executable, '-c', 'import sys; sys.exit(3)']
    guard = subprocess.Popen([sys.executable, '-I', str(builtin_recall.GUARD), *server], stdin=subprocess.PIPE,
                             stderr=subprocess.PIPE)
    assert guard.wait(timeout=30) == 3
    assert b'Fatal Python error' not in guard.stderr.read()
    guard.stdin.close()
