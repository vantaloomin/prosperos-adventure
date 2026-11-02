"""Launch buttons for local programs (dungeon/launcher.py) and starting them with the Dungeon."""
import asyncio
import os
import time
from pathlib import Path

import httpx
import pytest

from dungeon import local_programs
from dungeon.errors import DomainError


class FakePrograms:
    """Stands in for the programs: nothing answers until something was started."""

    def __init__(self, exit_code=None):
        self.started: list[list[str]] = []
        self.folders: list[str] = []
        self.up: set[int] = set()
        self.exit_code = exit_code

    def listen(self, command, options):
        self.started.append(command)
        self.folders.append(options.get('cwd'))
        host = (options.get('env') or {}).get('OLLAMA_HOST', '')
        # A launch script stands in for ComfyUI started on its usual port.
        self.up.add(int(command[command.index('--port') + 1]) if '--port' in command else int(host.rpartition(':')[2] or 8188))

    def spawn(self, command, **options):
        self.listen(command, options)
        program = self

        class Process:
            def poll(self):
                return program.exit_code
        return Process()

    def run(self, command, **options):
        if '--port' in command:
            self.listen(command, options)
        else:
            self.started.append(command)

        class Done:
            returncode = 0
        return Done()

    def transport(self):
        def answer(request):
            if request.url.port not in self.up or self.exit_code is not None:
                raise httpx.ConnectError('refused', request=request)
            return httpx.Response(200, json={})
        return httpx.MockTransport(answer)


@pytest.fixture
def programs(app, tmp_path):
    fake = FakePrograms()
    launcher = app.state.launcher
    launcher.spawn, launcher.run, launcher.transport = fake.spawn, fake.run, fake.transport()
    lms = tmp_path / 'lms.exe'
    lms.write_bytes(b'')
    comfy = tmp_path / 'ComfyUI_windows_portable'
    (comfy / 'python_embeded').mkdir(parents=True)
    launcher.finders = {'lmstudio': lambda: lms, 'ollama': lambda: None, 'kobold': lambda: None, 'comfyui': lambda: comfy}
    return fake


def add_profile(client, config, name):
    response = client.post('/api/models/profiles', json={'name': name, 'config': config})
    assert response.status_code == 201, response.text


def setup_programs(client):
    add_profile(client, {'provider': 'local', 'model': 'qwen3-8b', 'context_tokens': 16384}, 'Local chat')
    add_profile(client, {'provider': 'anthropic', 'model': 'claude-sonnet-5-5'}, 'Hosted')
    response = client.post('/api/images/backends', json={'kind': 'comfyui', 'base_url': 'http://127.0.0.1:8188',
                                                          'accept_disclosure': True})
    assert response.status_code in (200, 201), response.text


def wait_for(client, program, state):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        found = {item['program']: item for item in client.get('/api/models/launcher').json()['programs']}[program]
        if found['state'] == state:
            return found
        time.sleep(0.05)
    raise AssertionError(f'{program} never became {state}: {found}')


def test_only_programs_on_this_computer_are_listed_in_start_order(client, programs):
    setup_programs(client)
    listing = client.get('/api/models/launcher').json()
    assert listing['auto_launch'] is False
    assert [item['program'] for item in listing['programs']] == ['lmstudio', 'comfyui']
    lmstudio = listing['programs'][0]
    assert [use['name'] for use in lmstudio['used_by']] == ['Local chat']
    assert (lmstudio['address'], lmstudio['state'], lmstudio['path_chosen']) == ('http://127.0.0.1:1234', 'idle', False)
    assert lmstudio['path'].endswith('lms.exe')


def test_the_program_behind_a_profile_follows_its_provider_and_port():
    assert local_programs.text_program({'provider': 'local', 'base_url': 'http://127.0.0.1:1234/v1'}) == 'lmstudio'
    assert local_programs.text_program({'provider': 'local', 'base_url': 'http://localhost:11434/v1'}) == 'ollama'
    assert local_programs.text_program({'provider': 'kobold', 'base_url': 'http://127.0.0.1:5001/api/v1'}) == 'kobold'
    assert local_programs.text_program({'provider': 'compatible', 'base_url': 'http://127.0.0.1:8080/v1'}) is None
    assert local_programs.text_program({'provider': 'local', 'base_url': 'http://192.168.1.4:1234/v1'}) is None


def test_lm_studio_starts_its_server_then_loads_the_profile_model_with_its_context(client, programs):
    setup_programs(client)
    assert client.post('/api/models/launcher/lmstudio/launch').status_code == 200
    wait_for(client, 'lmstudio', 'running')
    assert [command[1:] for command in programs.started] == [
        ['server', 'start', '--port', '1234'], ['load', 'qwen3-8b', '--context-length', '16384', '-y']]


def test_comfyui_portable_starts_on_the_backend_port(client, programs):
    setup_programs(client)
    client.post('/api/models/launcher/comfyui/launch')
    wait_for(client, 'comfyui', 'running')
    command = programs.started[0]
    assert command[0].endswith('python.exe') and command[-4:] == ['--listen', '127.0.0.1', '--port', '8188']
    assert '--windows-standalone-build' in command


def test_a_program_that_stops_while_starting_says_so(client, programs, app):
    setup_programs(client)
    programs.exit_code = 1
    app.state.launcher.folder.mkdir(parents=True, exist_ok=True)
    client.post('/api/models/launcher/comfyui/launch')
    failed = wait_for(client, 'comfyui', 'failed')
    assert 'ComfyUI stopped while starting' in failed['message']


def test_a_program_not_found_asks_for_its_path_and_a_wrong_path_is_refused(client, programs, app, tmp_path):
    add_profile(client, {'provider': 'local', 'model': 'llama3', 'base_url': 'http://127.0.0.1:11434/v1'}, 'Ollama')
    client.post('/api/models/launcher/ollama/launch')
    assert 'was not found on this PC' in wait_for(client, 'ollama', 'failed')['message']
    assert client.put('/api/models/launcher/ollama', json={'path': str(tmp_path / 'missing.exe')}).status_code == 422
    ollama = tmp_path / 'ollama.exe'
    ollama.write_bytes(b'')
    listing = client.put('/api/models/launcher/ollama', json={'path': str(ollama)}).json()
    assert (listing['programs'][0]['path'], listing['programs'][0]['path_chosen']) == (str(ollama), True)
    client.post('/api/models/launcher/ollama/launch')
    wait_for(client, 'ollama', 'running')
    assert programs.started[-1] == [str(ollama), 'serve']


def test_koboldcpp_needs_the_model_file(client, programs, app, tmp_path):
    kobold = tmp_path / 'koboldcpp.exe'
    kobold.write_bytes(b'')
    app.state.launcher.finders['kobold'] = lambda: kobold
    add_profile(client, {'provider': 'kobold', 'model': 'koboldcpp/unfindable-model', 'context_tokens': 8192}, 'Kobold')
    assert client.get('/api/models/launcher').json()['programs'][0]['needs_model'] is True
    model = tmp_path / 'unfindable-model.gguf'
    model.write_bytes(b'')
    client.put('/api/models/launcher/kobold', json={'model_path': str(model)})
    client.post('/api/models/launcher/kobold/launch')
    wait_for(client, 'kobold', 'running')
    assert programs.started[-1] == [str(kobold), '--model', str(model), '--port', '5001', '--gpulayers', '-1',
                                    '--skiplauncher', '--contextsize', '8192']


def test_starting_with_the_companion_is_off_until_turned_on_then_runs_in_order(client, programs, app):
    setup_programs(client)
    asyncio.run(app.state.launcher.launch_all())
    assert programs.started == []
    assert client.put('/api/models/launcher', json={'auto_launch': True}).json()['auto_launch'] is True
    asyncio.run(app.state.launcher.launch_all())
    assert [Path(command[0]).name for command in programs.started] == ['lms.exe', 'lms.exe', 'python.exe']


def test_installs_are_found_a_few_folders_down(tmp_path):
    portable = tmp_path / 'AI' / 'ComfyUI_windows_portable'
    (portable / 'python_embeded').mkdir(parents=True)
    (tmp_path / 'Tools').mkdir()
    (tmp_path / 'Tools' / 'koboldcpp').write_bytes(b'')
    assert local_programs.search([tmp_path], local_programs.is_comfy_folder) == portable
    if not local_programs.WINDOWS:
        assert local_programs.search([tmp_path], local_programs.is_kobold) == tmp_path / 'Tools' / 'koboldcpp'


def test_a_folder_without_comfyui_is_refused(client, programs, tmp_path):
    setup_programs(client)
    empty = tmp_path / 'Downloads'
    empty.mkdir()
    refused = client.put('/api/models/launcher/comfyui', json={'path': str(empty)})
    assert refused.status_code == 422 and "doesn't look like ComfyUI" in refused.json()['detail']
    (empty / 'main.py').write_text('')
    (empty / 'comfy').mkdir()
    assert client.put('/api/models/launcher/comfyui', json={'path': str(empty)}).status_code == 200


@pytest.mark.parametrize(('error', 'said'), [
    (PermissionError(13, 'Permission denied'), "didn't allow it to run"),
    (FileNotFoundError(2, 'No such file'), 'nothing is at that location'),
    (OSError(8, 'Exec format error'), "isn't a program"),
    (OSError(5, 'Input/output error'), 'details are in the log'),
])
def test_a_program_that_cannot_be_opened_says_why_in_plain_words(client, programs, app, error, said):
    setup_programs(client)

    def refuse(command, **options):
        raise error
    app.state.launcher.spawn = refuse
    client.post('/api/models/launcher/comfyui/launch')
    failed = wait_for(client, 'comfyui', 'failed')
    assert failed['message'].startswith("ComfyUI couldn't start") and said in failed['message']
    assert 'Errno' not in failed['message'] and failed['detail'] == error.strerror


def test_a_path_from_the_home_folder_can_start_with_a_tilde(client, programs, tmp_path, monkeypatch):
    add_profile(client, {'provider': 'local', 'model': 'llama3', 'base_url': 'http://127.0.0.1:11434/v1'}, 'Ollama')
    monkeypatch.setenv('HOME', str(tmp_path))
    monkeypatch.setenv('USERPROFILE', str(tmp_path))
    (tmp_path / 'ollama').write_bytes(b'')
    listing = client.put('/api/models/launcher/ollama', json={'path': '~/ollama'}).json()
    assert listing['programs'][0]['path'] == str(tmp_path / 'ollama') and listing['system'] in {'windows', 'mac', 'linux'}


def test_comfyui_launch_script_runs_as_it_is(client, programs, app, tmp_path):
    setup_programs(client)
    for name in ('run_nvidia_gpu.bat', 'start comfy.cmd', 'comfy.sh', 'ComfyUI.command'):
        script = tmp_path / name
        script.write_text('python main.py --port 8188\n')
        programs.up.clear()
        assert client.put('/api/models/launcher/comfyui', json={'path': str(script)}).status_code == 200
        client.post('/api/models/launcher/comfyui/launch')
        wait_for(client, 'comfyui', 'running')
        command = programs.started[-1]
        assert command[-1] == str(script) and '--port' not in command
        assert (command[1] == '/c') == (script.suffix in {'.bat', '.cmd'})
        assert programs.folders[-1] == str(tmp_path)


def test_a_comfyui_folder_never_runs_on_this_apps_own_python(tmp_path, monkeypatch):
    folder = tmp_path / 'ComfyUI'
    (folder / 'comfy').mkdir(parents=True)
    (folder / 'main.py').write_text('')
    own = tmp_path / 'companion-env'
    system = tmp_path / 'system'
    outside = system / 'python3'
    monkeypatch.setattr(local_programs.sys, 'prefix', str(own))
    # This app's environment first on PATH, the system Python (also named python3) behind it.
    monkeypatch.setenv('PATH', os.pathsep.join([str(own / 'bin'), str(system)]))
    paths = {(str(own / 'bin'), 'python3'): str(own / 'bin' / 'python3'), (str(system), 'python3'): str(outside)}
    monkeypatch.setattr(local_programs.shutil, 'which', lambda name, path=None: paths.get((path, name)))
    assert local_programs.comfy_command(folder, 8188)[:2] == [str(outside), str(folder / 'main.py')]
    del paths[(str(system), 'python3')]
    with pytest.raises(DomainError, match='no Python of its own'):
        local_programs.comfy_command(folder, 8188)
    monkeypatch.setattr(local_programs.shutil, 'which', lambda name, path=None: None)
    with pytest.raises(DomainError, match='no Python of its own'):
        local_programs.comfy_command(folder, 8188)
    venv = folder / ('venv/Scripts/python.exe' if local_programs.WINDOWS else 'venv/bin/python3')
    venv.parent.mkdir(parents=True)
    venv.write_bytes(b'')
    assert local_programs.comfy_command(folder, 8188)[0] == str(venv)
