"""Image jobs, content routing and backend adapters (PRD F3–F9)."""
import asyncio
import base64
import json
import os
import struct
import sys

import httpx
import pytest
from fastapi.testclient import TestClient

from dungeon.identity import CLIENT_HEADER
from dungeon.images import backends, content
from dungeon.images.adapters.base import AdapterError, ImageRequest, ImageResult
from dungeon.images.adapters.codex import CodexAdapter
from dungeon.images.adapters.comfyui import ComfyAdapter
from dungeon.images.adapters.hosted import HostedAdapter, image_models
from dungeon.main import create_app
from dungeon.providers.vault import MemoryVault


def png(width=64, height=48) -> bytes:
    return b'\x89PNG\r\n\x1a\n' + b'\x00\x00\x00\rIHDR' + struct.pack('>II', width, height) + b'\x08\x02\x00\x00\x00'


class FakeAdapter:
    """Records requests; `outcomes` scripts results (bytes) or AdapterErrors in order."""

    def __init__(self):
        self.requests = []
        self.outcomes = []
        self.gate = None

    async def generate(self, request):
        self.requests.append(request)
        if self.gate:
            await self.gate.wait()
        outcome = self.outcomes.pop(0) if self.outcomes else png()
        if isinstance(outcome, Exception):
            raise outcome
        return ImageResult(outcome, model='fake-model', seed=request.seed)

    async def check(self, backend, config, key=None):
        from dungeon.images.adapters.base import Check
        return Check(True, 'fine')


@pytest.fixture
def adapters():
    return {'comfyui': FakeAdapter(), 'codex': FakeAdapter(), 'hosted': FakeAdapter()}


@pytest.fixture
def app(tmp_path, clock, provider, adapters):
    return create_app(tmp_path / 'workspace' / 'dungeon.sqlite3', clock=clock, vault=MemoryVault(),
                      provider=provider, background=False, image_adapters=adapters)


@pytest.fixture
def client(app):
    with TestClient(app, headers={CLIENT_HEADER: 'workspace'}) as test_client:
        yield test_client


def ok(response):
    assert response.status_code == 200, response.text
    return response.json()


def add_backend(client, **body):
    body.setdefault('accept_disclosure', True)
    return ok(client.post('/api/images/backends', json=body))


def local_comfy(client):
    return add_backend(client, kind='comfyui', base_url='http://127.0.0.1:8188')


def drain(client):
    asyncio.run(client.app.state.images.drain())


def generate(client, post, **body):
    return ok(client.post('/api/images/jobs', json={'post_id': post['id'], **body}))


LABELLED = [
    ('Mira reads a novel at a quiet café by the window.', 'safe'),
    ('Mira jogs along the river at sunrise in running gear.', 'safe'),
    ('Mira laughs with friends at a crowded jazz bar.', 'safe'),
    ('Mira graduates magna cum laude in a cap and gown.', 'safe'),
    ('Mira swims at the beach in a swimsuit on a sunny day.', 'safe'),
    ('Mira posing nude on a bed.', 'nsfw'),
    ('An erotic scene in the bedroom.', 'nsfw'),
    ('Mira in lingerie by the mirror.', 'nsfw'),
    ('A seductive look over the shoulder.', 'nsfw'),
    ('A battlefield of dismembered bodies and gore.', 'nsfw'),
    ('Mira, t-o-p-l-e-s-s, at the lake.', 'nsfw'),
    ('Mira, n a k e d, in the rain.', 'nsfw'),
    ('A nude 16-year-old at the beach.', 'prohibited'),
    ('Sexual pose with a schoolgirl outfit on a teen.', 'prohibited'),
    ('Nude photo of a famous actress.', 'prohibited'),
    ('A rape scene.', 'prohibited'),
    ('Non-consensual encounter in an alley.', 'prohibited'),
]


@pytest.mark.parametrize(('prompt', 'expected'), LABELLED)
def test_labelled_prompts_classify_as_expected(prompt, expected):
    assert content.classify({'prompt': prompt}).tier == expected


def test_known_false_positives_are_recorded_not_tuned_away():
    """Fail-closed lists catch some harmless wording; these stay off hosted backends (F6)."""
    for prompt in ('Mira ordered chicken breasts at the diner.', 'Mira donated blood at the clinic.'):
        assert content.classify({'prompt': prompt}).tier == 'nsfw'


def test_a_safe_prompt_from_a_sexual_event_is_not_safe():
    request = {'prompt': 'Mira smiles in soft morning light.',
               'events': [{'summary': 'Mira and Dan had sex after the party.'}]}
    assert content.classify(request).tier == 'nsfw'


def test_classifier_errors_and_manual_marks_route_as_nsfw(monkeypatch):
    assert content.classify({'prompt': 'A park bench.', 'marked_nsfw': True}).tier == 'nsfw'

    def broken(_text):
        raise RuntimeError('boom')
    monkeypatch.setattr(content, 'matches', broken)
    result = content.classify({'prompt': 'A park bench.'})
    assert result.tier == 'nsfw' and 'classifier error' in result.reasons[0]


# Routing and jobs ----------------------------------------------------------------------------


def test_a_backend_style_never_makes_a_server_less_strict(client):
    hosted = add_backend(client, kind='hosted', provider='openrouter', model='m', api_key='k')
    refused = client.put(f"/api/images/backends/{hosted['id']}", json={'style': 'Erotic nude photograph'})
    assert refused.status_code == 422 and 'takes NSFW requests' in refused.json()['detail']
    created = client.post('/api/images/backends', json={'kind': 'codex', 'style': 'Erotic nude photograph',
                                                        'accept_disclosure': True})
    assert created.status_code == 422
    local = local_comfy(client)
    assert ok(client.put(f"/api/images/backends/{local['id']}", json={'style': 'Erotic nude photograph'}))['style']


# Adapters against stand-in servers --------------------------------------------------------------

def request_for(kind, config, **values) -> ImageRequest:
    base = {'job_id': 'job1', 'prompt': 'A café', 'negative': 'text', 'seed': 7, 'width': 1024, 'height': 1024,
            'backend': {'kind': kind, 'provider': values.pop('provider', kind)}, 'config': config}
    return ImageRequest(**{**base, **values})


class ComfyStandIn:
    def __init__(self, history_status='success'):
        self.prompts = []
        self.deleted = []
        self.interrupted = []
        self.history_calls = 0
        self.history_status = history_status
        self.pending = True
        self.info_calls = []

    def __call__(self, request: httpx.Request):
        path = request.url.path
        if path == '/prompt':
            self.prompts.append(json.loads(request.content)['prompt'])
            return httpx.Response(200, json={'prompt_id': 'p1', 'number': 1, 'node_errors': {}})
        if path == '/history/p1':
            self.history_calls += 1
            if self.history_calls < 2 or self.history_status == 'never':
                return httpx.Response(200, json={})
            if self.history_status == 'error':
                return httpx.Response(200, json={'p1': {'status': {'status_str': 'error', 'messages': [
                    ['execution_error', {'exception_message': 'CUDA out of memory'}]]}, 'outputs': {}}})
            return httpx.Response(200, json={'p1': {'status': {'status_str': 'success', 'completed': True},
                                                    'outputs': {'9': {'images': [{'filename': 'a.png', 'subfolder': '',
                                                                                  'type': 'output'}]}}}})
        if path == '/view':
            return httpx.Response(200, content=png(1024, 1024))
        if path == '/queue' and request.method == 'GET':
            return httpx.Response(200, json={'queue_running': [] if self.pending else [[1, 'p1', {}, {}, []]],
                                             'queue_pending': [[1, 'p1', {}, {}, []]] if self.pending else []})
        if path == '/queue':
            self.deleted.append(json.loads(request.content))
            return httpx.Response(200)
        if path == '/interrupt':
            self.interrupted.append(json.loads(request.content))
            return httpx.Response(200)
        if path.startswith('/object_info'):
            return self.object_info(request)
        return httpx.Response(404)

    def object_info(self, request: httpx.Request):
        """The whole node list for the check; one node's entry, from the user's files, for a listing."""
        if request.url.path == '/object_info':
            return httpx.Response(200, json={
                'UNETLoader': {'input': {'required': {'unet_name': [['other.safetensors'], {}],
                                                      'weight_dtype': [['default'], {}]}}},
                'CLIPTextEncode': {'input': {'required': {'text': ['STRING', {}], 'clip': ['CLIP']}}}})
        self.info_calls.append(str(request.url))
        return httpx.Response(200, json={key: value for key, value in USER_FILES.items()
                                         if request.url.path == f'/object_info/{key}'})


# A real Windows ComfyUI 0.39.0 lists files in subfolders with backslashes; they are kept exactly.
MODEL = 'Krea 2\\Muse by Stable Yogi Krea2 V3.5 Civ NVFP4 C84.safetensors'
ENCODER = 'LLM\\qwen3-vl-4b-heretic_nvfp4.safetensors'
VAE = 'Qwen\\qwenImageVAESharpKrea2_bf16.safetensors'
PHONE = 'Krea 2\\phone_photography_2025_krea2.safetensors'
# The user's own files, in both of ComfyUI's combo formats (the newer one is ["COMBO", {"options": [...]}]).
USER_FILES = {
    'UNETLoader': {'input': {'required': {
        'unet_name': [[MODEL, 'krea2_turbo_fp8_scaled.safetensors']],
        'weight_dtype': [['default', 'fp8_e4m3fn']]}}},
    'CLIPLoader': {'input': {'required': {
        'clip_name': ['COMBO', {'options': [ENCODER]}],
        'type': ['COMBO', {'options': ['stable_diffusion', 'krea2']}]}, 'optional': {'device': [['default', 'cpu']]}}},
    'VAELoader': {'input': {'required': {'vae_name': [[VAE, 'pixel_space']]}}},
    'LoraLoaderModelOnly': {'input': {'required': {'lora_name': [[PHONE, 'sdxl\\detail.safetensors', 'prospero-x.safetensors']],
                                                   'strength_model': ['FLOAT', {}]}}},
    'KSampler': {'input': {'required': {'sampler_name': [['euler', 'res_multistep']], 'scheduler': [['simple', 'beta']],
                                        'steps': ['INT', {}], 'cfg': ['FLOAT', {}]}}},
}
CHOSEN = {'unet_name': MODEL, 'clip_name': ENCODER, 'vae_name': VAE}


def test_comfyui_fills_the_krea2_template_and_fetches_the_output():
    server = ComfyStandIn()
    adapter = ComfyAdapter(httpx.MockTransport(server), poll_seconds=0)
    result = asyncio.run(adapter.generate(request_for('comfyui', {'base_url': 'http://127.0.0.1:8188'})))
    graph = server.prompts[0]
    assert graph['4']['inputs']['text'] == 'A café' and graph['5']['class_type'] == 'ConditioningZeroOut'
    assert graph['7']['inputs']['seed'] == 7 and graph['6']['inputs']['width'] == 1024
    assert result.data.startswith(b'\x89PNG') and result.model == 'krea2_turbo_fp8_scaled.safetensors'
    assert result.workflow == 'krea2-turbo' and result.remote_id == 'p1'


def test_comfyui_reports_execution_errors_and_timeouts():
    adapter = ComfyAdapter(httpx.MockTransport(ComfyStandIn('error')), poll_seconds=0)
    with pytest.raises(AdapterError) as error:
        asyncio.run(adapter.generate(request_for('comfyui', {'base_url': 'http://127.0.0.1:8188'})))
    assert 'CUDA out of memory' in error.value.message
    server = ComfyStandIn('never')
    adapter = ComfyAdapter(httpx.MockTransport(server), poll_seconds=0.001, timeout_seconds=0.05)
    with pytest.raises(AdapterError) as timeout:
        asyncio.run(adapter.generate(request_for('comfyui', {'base_url': 'http://127.0.0.1:8188'})))
    assert timeout.value.code == 'timeout' and server.deleted == [{'delete': ['p1']}] and server.interrupted == []


def test_comfyui_cancel_interrupts_only_its_own_running_prompt():
    server = ComfyStandIn('never')
    server.pending = False
    adapter = ComfyAdapter(httpx.MockTransport(server), poll_seconds=0.001)

    async def scenario():
        task = asyncio.create_task(adapter.generate(request_for('comfyui', {'base_url': 'http://127.0.0.1:8188'})))
        await asyncio.sleep(0.02)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    asyncio.run(scenario())
    assert server.interrupted == [{'prompt_id': 'p1'}] and server.deleted == []


def test_comfyui_check_lists_missing_nodes_and_models():
    adapter = ComfyAdapter(httpx.MockTransport(ComfyStandIn()))
    report = asyncio.run(adapter.check({}, {'base_url': 'http://127.0.0.1:8188'}))
    assert not report.ok
    assert any('krea2_turbo_fp8_scaled.safetensors' in line for line in report.details)
    assert any('Missing node: CLIPLoader' in line for line in report.details)


def test_comfyui_lists_the_servers_files_for_each_loader():
    server = ComfyStandIn()
    adapter = ComfyAdapter(httpx.MockTransport(server))
    files = asyncio.run(adapter.files({'base_url': 'http://127.0.0.1:8188'}))
    assert files == {'unet_name': [MODEL, 'krea2_turbo_fp8_scaled.safetensors'], 'clip_name': [ENCODER],
                     'clip_type': ['stable_diffusion', 'krea2'], 'vae_name': [VAE, 'pixel_space'],
                     'ref_unet_name': [MODEL, 'krea2_turbo_fp8_scaled.safetensors'],
                     'lora': [PHONE, 'sdxl\\detail.safetensors', 'prospero-x.safetensors'],
                     'sampler_name': ['euler', 'res_multistep'], 'scheduler': ['simple', 'beta']}
    assert server.info_calls == [f'http://127.0.0.1:8188/object_info/{name}'
                                 for name in ('UNETLoader', 'CLIPLoader', 'VAELoader', 'UnetLoaderGGUF', 'LoraLoaderModelOnly',
                                              'KSampler')]


def test_comfyui_puts_chosen_files_in_the_built_in_workflow_only():
    server = ComfyStandIn()
    adapter = ComfyAdapter(httpx.MockTransport(server), poll_seconds=0)
    config = {'base_url': 'http://127.0.0.1:8188', **CHOSEN}
    result = asyncio.run(adapter.generate(request_for('comfyui', config)))
    graph = server.prompts[0]
    assert graph['1']['inputs']['unet_name'] == CHOSEN['unet_name'] and result.model == CHOSEN['unet_name']
    assert graph['2']['inputs'] == {'clip_name': CHOSEN['clip_name'], 'type': 'krea2'}
    assert graph['3']['inputs']['vae_name'] == CHOSEN['vae_name']
    custom = {'1': {'class_type': 'UNETLoader', 'inputs': {'unet_name': 'mine.safetensors'}},
              '2': {'class_type': 'CLIPTextEncode', 'inputs': {'text': '{{prompt}}'}}}
    asyncio.run(adapter.generate(request_for('comfyui', {**config, 'workflow': json.dumps(custom)})))
    assert server.prompts[1]['1']['inputs']['unet_name'] == 'mine.safetensors'


def test_comfyui_check_reports_the_chosen_files():
    def server(request):
        if request.url.path == '/object_info':
            return httpx.Response(200, json={**USER_FILES, **{name: {'input': {'required': {}}} for name in (
                'CLIPTextEncode', 'ConditioningZeroOut', 'EmptyLatentImage', 'KSampler', 'VAEDecode', 'SaveImage')}})
        return httpx.Response(404)
    adapter = ComfyAdapter(httpx.MockTransport(server))
    defaults = asyncio.run(adapter.check({}, {'base_url': 'http://127.0.0.1:8188'}))
    assert not defaults.ok and any('qwen_image_vae.safetensors' in line for line in defaults.details)
    chosen = asyncio.run(adapter.check({}, {'base_url': 'http://127.0.0.1:8188', **CHOSEN}))
    assert chosen.ok, chosen.details
    # The built-in reference workflow's own nodes and LoRA are only noted: profile pictures need them, other pictures don't.
    assert chosen.summary == ('ComfyUI has everything the built-in Krea 2 workflow needs. Pictures made from a reference need '
                              'the Krea 2 Identity Edit nodes and the files under Details first.')
    assert any('Krea2EditModelPatch' in line and 'Krea 2 Identity Edit nodes' in line for line in chosen.details)
    assert any('krea2_identity_edit_v1_2.safetensors' in line for line in chosen.details)
    assert chosen.install == [{'id': 'krea2edit', 'label': 'Krea 2 Identity Edit'}]
    missing = asyncio.run(adapter.check({}, {'base_url': 'http://127.0.0.1:8188', **CHOSEN, 'vae_name': 'gone.safetensors'}))
    assert missing.details == ['Missing file or option for VAELoader.vae_name: gone.safetensors.']
    # The subfolder is part of the name: the bare file name is not the server's file.
    bare = asyncio.run(adapter.check({}, {'base_url': 'http://127.0.0.1:8188', **CHOSEN,
                                          'clip_name': 'qwen3-vl-4b-heretic_nvfp4.safetensors'}))
    assert bare.details == ['Missing file or option for CLIPLoader.clip_name: qwen3-vl-4b-heretic_nvfp4.safetensors.']


@pytest.fixture
def comfy_client(tmp_path, clock, provider):
    def handler(request):
        if request.url.host == 'down.example':
            raise httpx.ConnectError('refused')
        return stand_in(request)
    stand_in = ComfyStandIn()
    adapters = {'comfyui': ComfyAdapter(httpx.MockTransport(handler)), 'codex': FakeAdapter(), 'hosted': FakeAdapter()}
    app = create_app(tmp_path / 'workspace' / 'dungeon.sqlite3', clock=clock, vault=MemoryVault(),
                     provider=provider, background=False, image_adapters=adapters)
    with TestClient(app, headers={CLIENT_HEADER: 'workspace'}) as test_client:
        yield test_client


def test_backend_model_files_are_saved_listed_and_cleared(comfy_client):
    backend = local_comfy(comfy_client)
    assert backend['model_files'] == {'unet_name': '', 'clip_name': '', 'clip_type': '', 'vae_name': '', 'ref_unet_name': ''}
    listed = ok(comfy_client.get(f"/api/images/backends/{backend['id']}/files"))
    assert listed['ok'] and listed['options']['clip_name'] == [ENCODER]
    assert listed['defaults'] == {'unet_name': 'krea2_turbo_fp8_scaled.safetensors',
                                  'clip_name': 'qwen3vl_4b_fp8_scaled.safetensors', 'clip_type': 'krea2',
                                  'vae_name': 'qwen_image_vae.safetensors', 'ref_unet_name': ''}
    saved = ok(comfy_client.put(f"/api/images/backends/{backend['id']}", json={**CHOSEN, 'clip_type': 'krea2'}))
    assert saved['model_files'] == {**CHOSEN, 'clip_type': 'krea2', 'ref_unet_name': ''}
    details = ok(comfy_client.post(f"/api/images/backends/{backend['id']}/check"))['details']
    assert f"Missing file or option for UNETLoader.unet_name: {CHOSEN['unet_name']}." in details
    assert not any('krea2_turbo_fp8_scaled' in line for line in details)
    cleared = ok(comfy_client.put(f"/api/images/backends/{backend['id']}", json={'unet_name': '', 'label': 'GPU'}))
    assert cleared['model_files'] == {**CHOSEN, 'unet_name': '', 'clip_type': 'krea2', 'ref_unet_name': ''}
    bad = comfy_client.put(f"/api/images/backends/{backend['id']}", json={'vae_name': 'a\nb.safetensors'})
    assert bad.status_code == 422


def test_backend_files_from_an_unreachable_server_or_another_kind(comfy_client):
    down = add_backend(comfy_client, kind='comfyui', base_url='http://down.example:8188', controlled_machine=True)
    listed = ok(comfy_client.get(f"/api/images/backends/{down['id']}/files"))
    assert not listed['ok'] and 'Cannot reach' in listed['error'] and listed['options']['unet_name'] == []
    assert listed['defaults']['vae_name'] == 'qwen_image_vae.safetensors'
    codex = add_backend(comfy_client, kind='codex')
    assert comfy_client.get(f"/api/images/backends/{codex['id']}/files").status_code == 422
    assert codex['model_files'] is None
    assert ok(comfy_client.put(f"/api/images/backends/{codex['id']}", json={'unet_name': 'x'}))['model_files'] is None


def test_backend_files_put_krea_2_files_first_and_style_loras_are_saved(comfy_client):
    """The lists only sort: Krea 2's files (by name or folder, or the Qwen encoder and VAE it uses)
    come first and are named in `matching`; nothing is hidden for not matching."""
    backend = local_comfy(comfy_client)
    listed = ok(comfy_client.get(f"/api/images/backends/{backend['id']}/files"))
    assert listed['options']['unet_name'] == [MODEL, 'krea2_turbo_fp8_scaled.safetensors']
    assert listed['matching']['clip_name'] == [ENCODER] and listed['matching']['vae_name'] == [VAE]
    assert listed['options']['lora'][0] == PHONE and listed['matching']['lora'] == [PHONE]
    assert 'sdxl\\detail.safetensors' in listed['options']['lora']
    assert backend['style_loras'] == []
    style = {'name': PHONE, 'strength': 0.7, 'trigger': 'phone photo'}
    saved = ok(comfy_client.put(f"/api/images/backends/{backend['id']}", json={'style_loras': [style]}))
    assert saved['style_loras'] == [style]
    details = ok(comfy_client.post(f"/api/images/backends/{backend['id']}/check"))['details']
    assert 'Missing node: LoraLoaderModelOnly, which applies LoRAs.' in details  # This stand-in has no LoRA node.
    info = {'LoraLoaderModelOnly': USER_FILES['LoraLoaderModelOnly']}
    assert ComfyAdapter.lora_problems(info, None, [style]) == []
    assert ComfyAdapter.lora_problems(info, 'prospero-x.safetensors', [{'name': 'gone.safetensors'}]) == [
        "The style LoRA gone.safetensors is not in ComfyUI's loras folder."]
    assert ok(comfy_client.put(f"/api/images/backends/{backend['id']}", json={'style_loras': []}))['style_loras'] == []
    too_many = comfy_client.put(f"/api/images/backends/{backend['id']}", json={'style_loras': [style] * 4})
    assert too_many.status_code == 422


def test_sampling_starts_on_krea_2_turbo_and_follows_the_users_choice(comfy_client):
    """Steps, CFG, sampler and scheduler per backend for the built-in workflow; a value equal to the
    workflow's own is stored as unset, and the job's workflow name records what it used."""
    backend = local_comfy(comfy_client)
    assert backend['sampler'] == {'steps': None, 'cfg': None, 'sampler_name': None, 'scheduler': None}
    listed = ok(comfy_client.get(f"/api/images/backends/{backend['id']}/files"))
    assert listed['sampler_defaults'] == {'steps': 8, 'cfg': 1.0, 'sampler_name': 'euler_ancestral', 'scheduler': 'simple'}
    assert listed['options']['sampler_name'] == ['euler', 'res_multistep'] and listed['options']['scheduler'] == ['simple', 'beta']
    tuned = ok(comfy_client.put(f"/api/images/backends/{backend['id']}",
                                json={'steps': 10, 'cfg': 1.0, 'sampler_name': 'res_multistep', 'scheduler': 'beta'}))
    assert tuned['sampler'] == {'steps': 10, 'cfg': None, 'sampler_name': 'res_multistep', 'scheduler': 'beta'}
    reset = ok(comfy_client.put(f"/api/images/backends/{backend['id']}",
                                json={'steps': 8, 'cfg': 1.0, 'sampler_name': 'euler_ancestral', 'scheduler': 'simple'}))
    assert reset['sampler'] == {'steps': None, 'cfg': None, 'sampler_name': None, 'scheduler': None}
    assert comfy_client.put(f"/api/images/backends/{backend['id']}", json={'steps': 0}).status_code == 422
    server = ComfyStandIn()
    adapter = ComfyAdapter(httpx.MockTransport(server), poll_seconds=0)
    config = {'base_url': 'http://127.0.0.1:8188', 'steps': 10, 'scheduler': 'beta'}
    result = asyncio.run(adapter.generate(request_for('comfyui', config)))
    sampler = server.prompts[0]['7']['inputs']
    assert (sampler['steps'], sampler['cfg'], sampler['sampler_name'], sampler['scheduler']) == (10, 1.0, 'euler_ancestral', 'beta')
    assert result.workflow == 'krea2-turbo (10 steps, CFG 1, euler_ancestral/beta)'


def test_a_style_lora_never_makes_a_server_less_strict(comfy_client):
    """A LoRA whose name or trigger reads as adult content only goes on a server that accepts NSFW
    requests: one on this computer or one the user controls (F6)."""
    nsfw = {'name': 'nsfw_nude_krea2.safetensors', 'strength': 0.8, 'trigger': ''}
    remote = add_backend(comfy_client, kind='comfyui', base_url='http://gpu.example:8188')
    refused = comfy_client.put(f"/api/images/backends/{remote['id']}", json={'style_loras': [nsfw]})
    assert refused.status_code == 422 and 'this computer' in refused.json()['detail']
    safe = {'name': PHONE, 'strength': 0.7, 'trigger': 'phone photo'}
    assert ok(comfy_client.put(f"/api/images/backends/{remote['id']}", json={'style_loras': [safe]}))['style_loras'] == [safe]
    local = local_comfy(comfy_client)
    assert ok(comfy_client.put(f"/api/images/backends/{local['id']}", json={'style_loras': [nsfw]}))['style_loras'] == [nsfw]
    created = comfy_client.post('/api/images/backends', json={'kind': 'comfyui', 'base_url': 'http://gpu.example:8188',
                                                             'style_loras': [nsfw]})
    assert created.status_code == 422


def test_model_links_are_pages_with_a_licence_note(client):
    links = ok(client.get('/api/images/model-links'))['links']
    assert {link['role'] for link in links} == {'model', 'clip', 'vae', 'reference'}
    for link in links:
        assert link['url'].startswith('https://huggingface.co/') and '/resolve/' not in link['url']
        assert link['name'] and link['licence']
    assert any('Gated' in link['licence'] for link in links if link['url'].endswith('krea/Krea-2-Turbo'))


FAKE_CODEX = '''
import json, os, pathlib, sys
args = sys.argv[1:]
mode = os.environ.get("FAKE_CODEX_MODE", "ok")
if args == ["--version"]:
    print("codex-cli 0.160.1"); sys.exit(0)
if args == ["login", "status"]:
    print({"apikey": "Logged in using an API key - sk-***", "out": "Not logged in"}.get(mode, "Logged in using ChatGPT"))
    sys.exit(0)
# Codex reads its prompt as UTF-8 whatever the console code page is.
pathlib.Path(os.environ["FAKE_CLI_LOG"]).write_text(" ".join(args) + "\\n" + sys.stdin.buffer.read().decode("utf-8"),
                                                    encoding="utf-8")
emit = lambda event: print(json.dumps(event), flush=True)
emit({"type": "thread.started", "thread_id": "thread-1"})
emit({"type": "turn.started"})
if mode == "slow":
    import time; time.sleep(3)  # short: on Windows only the .cmd wrapper is killed
emit({"type": "error", "message": "Reconnecting... 1/5"})
if mode == "auth":
    emit({"type": "turn.failed", "error": {"message": "unexpected status 401 Unauthorized: token expired"}})
    sys.exit(1)
if mode == "refused":
    emit({"type": "turn.failed", "error": {"message": "Your request was rejected by the safety system"}})
    sys.exit(1)
if mode != "none":
    folder = pathlib.Path(os.environ["CODEX_HOME"]) / "generated_images" / "thread-1"
    folder.mkdir(parents=True, exist_ok=True)
    image = folder / "ig_1.png"
    image.write_bytes(bytes.fromhex(os.environ["FAKE_PNG"]))
    if mode == "ok":
        emit({"type": "item.completed", "item": {"type": "image_generation", "saved_path": str(image)}})
emit({"type": "item.completed", "item": {"type": "agent_message", "text": "DONE"}})
emit({"type": "turn.completed", "usage": {}})
'''


@pytest.fixture
def fake_codex(tmp_path, monkeypatch):
    """A stand-in `codex` launcher: a .cmd wrapper on Windows, a script with a shebang elsewhere."""
    home = tmp_path / 'codex-home'
    home.mkdir()
    (home / 'auth.json').write_text('{}')
    monkeypatch.setenv('CODEX_HOME', str(home))
    monkeypatch.setenv('FAKE_CLI_LOG', str(tmp_path / 'cli.log'))
    monkeypatch.setenv('FAKE_PNG', png(1024, 1536).hex())
    raw = tmp_path / 'raw'
    raw.mkdir()
    script = tmp_path / 'fake_codex.py'
    script.write_text(FAKE_CODEX)
    if os.name == 'nt':
        launcher = tmp_path / 'codex.cmd'
        launcher.write_text(f'@"{sys.executable}" "{script}" %*\n')
    else:
        launcher = tmp_path / 'codex'
        launcher.write_text(f'#!{sys.executable}\n{FAKE_CODEX}')
        launcher.chmod(0o755)
    return {'codex': launcher, 'home': home, 'log': tmp_path / 'cli.log', 'raw': raw}


def native_request(fake_codex, **values):
    return request_for('codex', {'cli_path': str(fake_codex['codex'])}, **{'width': 1024, 'height': 1536,
                       'raw_dir': fake_codex['raw'], **values})


def test_codex_native_runs_one_exec_turn_and_copies_the_saved_image(fake_codex):
    result = asyncio.run(CodexAdapter().generate(native_request(fake_codex)))
    args, prompt = fake_codex['log'].read_text(encoding='utf-8').split('\n', 1)
    assert args.startswith('exec --json --skip-git-repo-check --ephemeral --ignore-user-config --ignore-rules '
                           '--sandbox read-only --cd ') and args.endswith(' -')
    assert '1024x1536' in prompt and 'A café' in prompt and 'Avoid: text' in prompt
    assert result.raw_path == fake_codex['raw'] / 'job1.png' and result.data[:4] == b'\x89PNG'
    assert result.remote_id == 'thread-1' and result.workflow == 'codex exec' and result.seed is None


def test_codex_native_finds_the_image_in_the_thread_folder(fake_codex, monkeypatch):
    monkeypatch.setenv('FAKE_CODEX_MODE', 'folder')
    result = asyncio.run(CodexAdapter().generate(native_request(fake_codex)))
    assert result.raw_path.exists()


@pytest.mark.parametrize(('mode', 'code'), [('auth', 'auth'), ('refused', 'refused'), ('none', 'failed')])
def test_codex_native_failures(fake_codex, monkeypatch, mode, code):
    monkeypatch.setenv('FAKE_CODEX_MODE', mode)
    with pytest.raises(AdapterError) as error:
        asyncio.run(CodexAdapter().generate(native_request(fake_codex)))
    assert error.value.code == code and 'Reconnecting' not in error.value.message


@pytest.mark.parametrize(('mode', 'ok', 'words'), [('ok', True, 'experimental'), ('apikey', True, 'API key'),
                                                   ('out', False, 'not signed in')])


def hosted_server(responses, seen):
    def handler(request: httpx.Request):
        seen.append(request)
        return responses.pop(0)
    return httpx.MockTransport(handler)


def test_hosted_images_style_sends_only_the_prompt():
    seen = []
    body = {'data': [{'b64_json': base64.b64encode(png()).decode()}], 'usage': {'total_tokens': 10}}
    adapter = HostedAdapter(hosted_server([httpx.Response(200, json=body)], seen))
    request = request_for('hosted', {'base_url': 'https://generativelanguage.googleapis.com/v1beta/openai',
                                     'model': 'imagen-4', 'api_style': 'images'}, provider='google', key='g-key')
    result = asyncio.run(adapter.generate(request))
    sent = json.loads(seen[0].content)
    assert seen[0].url.path.endswith('/images/generations') and seen[0].headers['authorization'] == 'Bearer g-key'
    assert set(sent) == {'model', 'prompt', 'n', 'size', 'response_format'} and sent['size'] == '1024x1024'
    assert result.usage == {'total_tokens': 10} and result.data.startswith(b'\x89PNG')


def test_hosted_chat_style_reads_images_in_the_message():
    seen = []
    url = 'data:image/png;base64,' + base64.b64encode(png()).decode()
    body = {'id': 'gen-1', 'choices': [{'message': {'content': '', 'images': [{'image_url': {'url': url}}]}}],
            'usage': {'cost': 0.04}}
    adapter = HostedAdapter(hosted_server([httpx.Response(200, json=body)], seen))
    request = request_for('hosted', {'base_url': 'https://images.example.com/v1', 'model': 'google/gemini-image',
                                     'api_style': 'chat'}, provider='other', key='k')
    result = asyncio.run(adapter.generate(request))
    assert json.loads(seen[0].content)['modalities'] == ['image', 'text']
    assert result.usage == {'cost': 0.04} and result.remote_id == 'gen-1'


@pytest.mark.parametrize('model', ['black-forest-labs/flux.2-pro', 'google/gemini-2.5-flash-image'])
def test_openrouter_uses_its_image_api_for_any_image_model(model):
    """A FLUX model writes no text, so the chat route has no endpoint for it; the image API takes every model,
    including backends saved with the chat style."""
    seen = []
    body = {'data': [{'b64_json': base64.b64encode(png()).decode(), 'media_type': 'image/png'}], 'usage': {'cost': 0.03}}
    adapter = HostedAdapter(hosted_server([httpx.Response(200, json=body)], seen))
    request = request_for('hosted', {'base_url': 'https://openrouter.ai/api/v1', 'model': model, 'api_style': 'chat'},
                          provider='openrouter', key='k', width=768, height=1024, reference=png())
    result = asyncio.run(adapter.generate(request))
    sent = json.loads(seen[0].content)
    assert seen[0].url.path == '/api/v1/images' and sent['model'] == model and sent['aspect_ratio'] == '3:4'
    assert sent['input_references'][0]['image_url']['url'].startswith('data:image/png;base64,')
    assert result.usage == {'cost': 0.03} and result.data.startswith(b'\x89PNG')


@pytest.mark.parametrize(('width', 'height', 'ratio'), [(1024, 1024, '1:1'), (1536, 1024, '3:2'), (1024, 1536, '2:3'),
                                                        (1344, 768, '16:9'), (832, 1040, '4:5')])
def test_openrouter_sizes_become_the_nearest_aspect_ratio(width, height, ratio):
    from dungeon.images.adapters.hosted import aspect_ratio
    assert aspect_ratio(width, height) == ratio


@pytest.mark.parametrize(('response', 'code'), [
    (httpx.Response(401, json={}), 'auth'),
    (httpx.Response(429, json={}), 'rate_limited'),
    (httpx.Response(400, json={'error': {'code': 'content_policy_violation'}}), 'refused'),
    (httpx.Response(500, json={}), 'failed'),
    (httpx.Response(200, json={'choices': [{'finish_reason': 'content_filter', 'message': {}}]}), 'refused'),
    (httpx.Response(200, json={'choices': [{'message': {'content': 'Here you go'}}]}), 'invalid_output'),
])
def test_hosted_errors_are_typed(response, code):
    adapter = HostedAdapter(hosted_server([response], []))
    request = request_for('hosted', {'base_url': 'https://images.example.com/v1', 'model': 'm', 'api_style': 'chat'},
                          provider='other', key='k')
    with pytest.raises(AdapterError) as error:
        asyncio.run(adapter.generate(request))
    assert error.value.code == code


def test_storage_reads_jpeg_and_webp_headers():
    from dungeon.images import storage
    jpeg = b'\xff\xd8\xff\xe0' + struct.pack('>H', 16) + b'\x00' * 14 + b'\xff\xc0' + struct.pack('>HBHH', 17, 8, 600,
                                                                                                    800)
    assert storage.sniff(jpeg) == ('jpg', 800, 600)
    webp = b'RIFF' + b'\x00' * 4 + b'WEBPVP8X' + b'\x00' * 8 + (99).to_bytes(3, 'little') + (49).to_bytes(3, 'little')
    assert storage.sniff(webp) == ('webp', 100, 50)


def test_codex_missing_login_unverified_size_and_old_imagegen_location(fake_codex, monkeypatch):
    with pytest.raises(AdapterError) as size:
        asyncio.run(CodexAdapter().generate(native_request(fake_codex, width=1216, height=832)))
    assert size.value.code == 'incompatible'
    # A location saved for the retired chatgpt-imagegen method falls back to codex on PATH.
    monkeypatch.setenv('PATH', '')
    old = request_for('codex', {'cli_path': str(fake_codex['codex'].with_name('chatgpt-imagegen'))},
                      raw_dir=fake_codex['raw'])
    with pytest.raises(AdapterError) as missing_cli:
        asyncio.run(CodexAdapter().generate(old))
    assert missing_cli.value.code == 'unavailable' and 'Codex CLI' in missing_cli.value.message
    (fake_codex['home'] / 'auth.json').unlink()
    with pytest.raises(AdapterError) as signed_out:
        asyncio.run(CodexAdapter().generate(native_request(fake_codex)))
    assert signed_out.value.code == 'auth' and 'codex login' in signed_out.value.message


def test_codex_timeout_stops_the_process(fake_codex, monkeypatch):
    monkeypatch.setenv('FAKE_CODEX_MODE', 'slow')

    async def scenario():
        task = asyncio.create_task(CodexAdapter(timeout_seconds=1).generate(native_request(fake_codex)))
        await asyncio.sleep(0.5)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    asyncio.run(scenario())


def test_nanogpt_is_a_named_provider_that_can_take_nsfw(client):
    backend = add_backend(client, kind='hosted', provider='nanogpt', model='hidream-o1-image', api_key='k',
                          allows_nsfw=True)
    assert backend['base_url'] == 'https://nano-gpt.com/api/v1' and backend['api_style'] == 'images'
    assert backend['nsfw_switch'] is True and backend['accepts_nsfw'] is True


def test_a_base_url_copied_with_its_request_path_is_trimmed(client):
    backend = add_backend(client, kind='hosted', provider='other', model='m', api_key='k',
                          base_url='https://nano-gpt.com/api/v1/images/generations/')
    assert backend['base_url'] == 'https://nano-gpt.com/api/v1'


def model_list(seen, status=200, ids=('hidream-o1-image',)):
    def server(request):
        seen.append(str(request.url))
        if status != 200:
            return httpx.Response(status, text='<!DOCTYPE html>not found')
        return httpx.Response(200, json={'object': 'list', 'data': [{'id': model} for model in ids]})
    return HostedAdapter(httpx.MockTransport(server))


@pytest.mark.parametrize('provider,base', [('nanogpt', 'https://nano-gpt.com/api/v1'),
                                           ('other', 'https://api.nano-gpt.com/api/v1/images/generations')])
def test_nanogpt_check_reads_its_image_model_list(provider, base):
    seen = []
    report = asyncio.run(model_list(seen).check({'provider': provider},
                                                {'base_url': base, 'model': 'hidream-o1-image'}, 'k'))
    assert report.ok and seen[0].endswith('/api/v1/images/models')


def test_a_missing_model_list_points_at_the_base_url():
    seen = []
    report = asyncio.run(model_list(seen, status=404).check({'provider': 'other'},
                                                            {'base_url': 'https://images.example.com', 'model': 'm'}, 'k'))
    assert not report.ok and 'https://images.example.com/models' in report.summary
    assert any('/v1' in line for line in report.details)


def test_a_saved_base_url_with_a_request_path_still_generates():
    seen = []

    def server(request):
        seen.append(str(request.url))
        return httpx.Response(200, json={'data': [{'b64_json': base64.b64encode(png()).decode()}]})
    adapter = HostedAdapter(httpx.MockTransport(server))
    request = request_for('hosted', {'base_url': 'https://nano-gpt.com/api/v1/images/generations', 'model': 'm',
                                     'api_style': 'images'}, provider='other', key='k')
    asyncio.run(adapter.generate(request))
    assert seen == ['https://nano-gpt.com/api/v1/images/generations']


def test_an_image_api_connection_can_be_edited_in_place(client):
    backend = add_backend(client, kind='hosted', provider='other', model='m', api_key='k',
                          base_url='https://images.example.com/v1')
    edited = ok(client.put(f"/api/images/backends/{backend['id']}", json={
        'label': 'NanoGPT', 'model': 'hidream-o1-image', 'api_key': 'new',
        'base_url': 'https://nano-gpt.com/api/v1/images/generations', 'accept_disclosure': True}))
    assert (edited['label'], edited['model'], edited['base_url']) == \
        ('NanoGPT', 'hidream-o1-image', 'https://nano-gpt.com/api/v1')
    assert edited['enabled'] and edited['has_key']


def test_openrouter_lists_every_image_model_it_has():
    """OpenRouter's `/models` leaves out models that write no text (FLUX, Seedream, Recraft), so the list comes from its
    image list, without the SVG-only vector models a photo cannot show."""
    from dungeon.images.adapters import hosted
    body = {'data': [{'id': 'google/gemini-2.5-flash-image', 'name': 'Gemini 2.5 Flash Image',
                      'architecture': {'input_modalities': ['image', 'text'], 'output_modalities': ['image', 'text']}},
                     {'id': 'black-forest-labs/flux.2-pro', 'name': 'FLUX.2 Pro',
                      'architecture': {'input_modalities': ['text', 'image'], 'output_modalities': ['image']}},
                     {'id': 'recraft/recraft-v4.1-flash', 'name': 'Recraft V4.1 Flash',
                      'architecture': {'input_modalities': ['text'], 'output_modalities': ['image']}},
                     {'id': 'recraft/recraft-v4-vector', 'name': 'Recraft V4 Vector',
                      'architecture': {'input_modalities': ['text', 'image'], 'output_modalities': ['image']},
                      'supported_parameters': {'output_format': {'type': 'enum', 'values': ['svg']}}}]}
    seen = []

    def server(request):
        seen.append(request)
        return httpx.Response(200, json=body)
    models = asyncio.run(HostedAdapter(httpx.MockTransport(server)).models(
        'openrouter', {'base_url': 'https://openrouter.ai/api/v1'}))
    assert [model['id'] for model in models] == ['black-forest-labs/flux.2-pro', 'google/gemini-2.5-flash-image',
                                                 'recraft/recraft-v4.1-flash']
    assert seen[0].url.path == '/api/v1/images/models' and 'authorization' not in seen[0].headers
    # A model that reads text only cannot follow a picture, so the onboarding portraits pick another backend.
    config = {'base_url': 'https://openrouter.ai/api/v1', 'api_style': 'chat'}
    assert not hosted.takes_reference({**config, 'model': 'recraft/recraft-v4.1-flash'}, 'openrouter')
    assert hosted.takes_reference({**config, 'model': 'black-forest-labs/flux.2-pro'}, 'openrouter')
    assert hosted.takes_reference({**config, 'model': 'never-listed'}, 'openrouter')


@pytest.mark.parametrize('body,provider,expected', [
    ({'data': [{'id': 'gpt-image-1'}, {'id': 'gpt-4o'}, {'id': 'dall-e-3'}]}, 'openai', ['dall-e-3', 'gpt-image-1']),
    ({'data': [{'id': 'models/imagen-4.0-generate-001'}, {'id': 'models/gemini-2.5-pro'}]}, 'google',
     ['imagen-4.0-generate-001']),
    ({'models': {'hidream-o1-image': {'name': 'HiDream'}, 'flux-dev': {}}}, 'nanogpt', ['flux-dev', 'hidream-o1-image']),
    (['sdxl', 'flux'], 'other', ['flux', 'sdxl']),
])
def test_image_model_lists_in_each_shape(body, provider, expected):
    assert sorted(row['id'] for row in image_models(body, provider)) == expected


# Worlds -----------------------------------------------------------------------------------------




def test_an_image_api_with_no_key_uses_the_key_saved_for_its_text_service(client, app):
    client.post('/api/models/profiles', json={'name': 'Chat', 'config': {'provider': 'openrouter', 'model': 'a/b'},
                                              'api_key': 'or-key'})
    borrowing = add_backend(client, kind='hosted', provider='openrouter', model='m')
    elsewhere = add_backend(client, kind='hosted', provider='other', base_url='https://images.example/v1', model='m')
    assert borrowing['key_from'] == 'Chat' and not borrowing['has_key'] and elsewhere['key_from'] is None
    with app.state.database.connect() as connection:
        saved = backends.get(connection, borrowing['id'])
    assert backends.backend_key(app.state.database, app.state.vault, saved) == 'or-key'
