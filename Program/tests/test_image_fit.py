"""Krea 2 on a card too small for its built-in fp8 file: the app picks a file that fits (Vanta, 2026-10-28), and a
.gguf file runs through the ComfyUI-GGUF loader."""
import httpx
import pytest
from fastapi.testclient import TestClient

from dungeon import hardware
from dungeon.database import decode
from dungeon.hardware import Hardware
from dungeon.identity import CLIENT_HEADER
from dungeon.images import backends
from dungeon.images.adapters.comfyui import ComfyAdapter, built_in, model_file
from dungeon.main import create_app
from dungeon.providers.vault import MemoryVault
from tests.test_images import ComfyStandIn, FakeAdapter, local_comfy, ok


def card(name, memory):
    return {'index': 0, 'name': name, 'memory_gb': memory, 'usable_gb': memory, 'used_gb': None, 'shared': False}


def computer(*gpus):
    return {'system': 'Windows', 'cores': 16, 'memory_gb': 64.0, 'gpus': list(gpus), 'gpu_note': None}


RTX_5070 = card('NVIDIA GeForce RTX 5070', 11.9)


def test_sizes_come_from_krea_2s_real_files():
    # Comfy-Org/Krea-2: fp8 13.1 GB, NVFP4 7.7 GB, bf16 26.3 GB, plus working room.
    assert 13 < hardware.image_size_gb('krea2_turbo_fp8_scaled.safetensors') < 15
    assert 8 < hardware.image_size_gb('krea2_turbo_nvfp4.safetensors') < 10
    assert hardware.image_size_gb('krea2_turbo_bf16.safetensors') > 25
    assert hardware.image_size_gb('krea2_turbo-Q4_K_M.gguf') < hardware.image_size_gb('krea2_turbo-Q6_K.gguf')


@pytest.mark.parametrize(('gpu', 'pick'), [
    (RTX_5070, 'krea2_turbo_nvfp4.safetensors'),
    # NVFP4 only runs natively on RTX 50-series cards, so others get a GGUF that fits.
    (card('NVIDIA GeForce RTX 3080', 10.0), 'krea2_turbo-Q4_K_M.gguf'),
    (card('NVIDIA GeForce RTX 4060', 8.0), 'krea2_turbo-Q3_K_M.gguf'),
    # The built-in fp8 file fits, so it stays; nothing fits, so it stays and the warning says so.
    (card('NVIDIA GeForce RTX 4070 Ti SUPER', 16.0), None),
    (card('NVIDIA GeForce GTX 1650', 4.0), None),
    (None, None)])
def test_picks_the_krea_2_file_the_card_holds(gpu, pick):
    assert hardware.model_pick(gpu) == pick


def test_prefers_a_fitting_file_comfyui_already_has():
    have = ['Krea 2\\Krea-2-Turbo-Q4_K_M.gguf', 'krea2_turbo_fp8_scaled.safetensors', 'krea2_raw_fp8_scaled.safetensors',
            'Krea2 Edit Q4_K_M.gguf']
    assert hardware.model_pick(card('NVIDIA GeForce RTX 3080', 10.0), have) == 'Krea 2\\Krea-2-Turbo-Q4_K_M.gguf'
    assert hardware.model_pick(RTX_5070, [*have, 'Muse Krea2 NVFP4.safetensors']) == 'Muse Krea2 NVFP4.safetensors'
    # Nothing it has fits: the one to download.
    assert hardware.model_pick(RTX_5070, ['krea2_turbo_bf16.safetensors']) == 'krea2_turbo_nvfp4.safetensors'


def test_a_too_big_file_names_the_one_that_fits():
    image = {'id': 'b1', 'label': 'Local ComfyUI', 'base_url': 'http://127.0.0.1:8188',
             'unet': 'krea2_turbo_fp8_scaled.safetensors',
             'size_gb': hardware.image_size_gb('krea2_turbo_fp8_scaled.safetensors'), 'family': 'krea2'}
    # The server lacks it: where to put it, no button.
    found = hardware.check(computer(RTX_5070), [], [image], {}, {image['base_url']: ['flux.safetensors']})[0]
    assert found['text'] == ('Local ComfyUI: krea2_turbo_fp8_scaled.safetensors needs about 14 GB, and the NVIDIA GeForce '
                             'RTX 5070 has 12 GB. ComfyUI will keep the rest in system memory, so pictures will be slow. '
                             'krea2_turbo_nvfp4.safetensors (about 9.1 GB) fits. Put it in ComfyUI\'s '
                             'models/diffusion_models folder, then press Check.')
    assert 'action' not in found and found['after'] == 'Or use a hosted image service.'
    # The server has it: one press uses it.
    listed = {image['base_url']: ['krea2_turbo_nvfp4.safetensors']}
    found = hardware.check(computer(RTX_5070), [], [image], {}, listed)[0]
    assert found['action'] == {'label': 'Use krea2_turbo_nvfp4', 'backend_id': 'b1',
                               'unet_name': 'krea2_turbo_nvfp4.safetensors'}
    assert found['text'].endswith('fits.')
    lines = hardware.can_run(computer(RTX_5070))
    assert lines[1].startswith('Pictures: Krea 2 fits as krea2_turbo_nvfp4 (about 9.1 GB), but not beside')


def test_the_pick_is_used_until_the_user_chooses_a_model():
    config = {'base_url': 'http://127.0.0.1:8188', 'unet_fit': 'krea2_turbo_nvfp4.safetensors'}
    assert model_file(config) == 'krea2_turbo_nvfp4.safetensors'
    assert all(node['inputs']['unet_name'] == 'krea2_turbo_nvfp4.safetensors'
               for node in built_in(config, reference=True).values() if node['class_type'] == 'UNETLoader')
    assert model_file({**config, 'unet_name': 'mine.safetensors'}) == 'mine.safetensors'


def test_a_gguf_model_loads_through_the_gguf_loader():
    config = {'base_url': 'http://127.0.0.1:8188', 'unet_name': 'Krea 2\\krea2_turbo-Q5_K_M.gguf'}
    for workflow in (built_in(config), built_in(config, reference=True)):
        loaders = [node for node in workflow.values() if 'unet_name' in node['inputs']]
        assert loaders and all(node == {'class_type': 'UnetLoaderGGUF', 'inputs': {'unet_name': 'Krea 2\\krea2_turbo-Q5_K_M.gguf'}}
                               for node in loaders)
    # A reference model of its own keeps the plain loader when it is a .safetensors file.
    mixed = built_in({**config, 'ref_unet_name': 'krea2_edit.safetensors'}, reference=True)
    assert {node['class_type'] for node in mixed.values() if 'unet_name' in node['inputs']} == {'UNETLoader'}


def test_the_check_names_the_gguf_nodes_when_comfyui_lacks_them():
    workflow = built_in({'unet_name': 'krea2_turbo-Q4_K_M.gguf'})
    assert 'Missing node: UnetLoaderGGUF (from the ComfyUI-GGUF nodes, https://github.com/city96/ComfyUI-GGUF).' in \
        ComfyAdapter.node_problems({}, workflow)


GGUF_FILES = {'UnetLoaderGGUF': {'input': {'required': {'unet_name': [['Krea 2\\krea2_turbo-Q4_K_S.gguf'], {}]}}}}


class GgufStandIn(ComfyStandIn):
    """A server with the ComfyUI-GGUF nodes and one Krea 2 GGUF file."""

    def object_info(self, request: httpx.Request):
        if request.url.path == '/object_info/UnetLoaderGGUF':
            return httpx.Response(200, json=GGUF_FILES)
        response = super().object_info(request)
        if request.url.path == '/object_info':
            return httpx.Response(200, json={**response.json(), **GGUF_FILES})
        return response


@pytest.fixture
def small_card(tmp_path, clock, provider):
    adapters = {'comfyui': ComfyAdapter(httpx.MockTransport(GgufStandIn())), 'codex': FakeAdapter(), 'hosted': FakeAdapter()}
    app = create_app(tmp_path / 'workspace' / 'dungeon.sqlite3', clock=clock, vault=MemoryVault(), provider=provider,
                     background=False, image_adapters=adapters,
                     hardware=Hardware(scanner=lambda: computer(card('NVIDIA GeForce RTX 3080', 10.0)), device=lambda url: None))
    with TestClient(app, headers={CLIENT_HEADER: 'workspace'}) as test_client:
        yield test_client


def saved_config(client, backend_id):
    with client.app.state.database.connect() as connection:
        return decode(backends.get(connection, backend_id)['config'])


def test_a_new_krea_2_server_starts_on_a_file_its_card_holds(small_card):
    backend = local_comfy(small_card)
    assert backend['model_fit'] == 'krea2_turbo-Q4_K_M.gguf'
    assert saved_config(small_card, backend['id'])['unet_fit'] == 'krea2_turbo-Q4_K_M.gguf'
    report = ok(small_card.get('/api/hardware'))
    assert report['local_images'][0]['unet'] == 'krea2_turbo-Q4_K_M.gguf' and report['warnings'] == []
    # Once the server lists its files, a fitting one it has wins, and is what the picker shows as the default.
    listed = ok(small_card.get(f"/api/images/backends/{backend['id']}/files"))
    assert 'Krea 2\\krea2_turbo-Q4_K_S.gguf' in listed['options']['unet_name']
    assert listed['defaults']['unet_name'] == 'Krea 2\\krea2_turbo-Q4_K_S.gguf'
    # Asking the card again keeps that pick.
    ok(small_card.get('/api/hardware?fresh=true'))
    assert saved_config(small_card, backend['id'])['unet_fit'] == 'Krea 2\\krea2_turbo-Q4_K_S.gguf'
    # A picked file the server lacks is said plainly, not as a loader error.
    ok(small_card.put(f"/api/images/backends/{backend['id']}", json={}))
    with small_card.app.state.database.connect(write=True) as connection:
        connection.execute("UPDATE image_backends SET config=json_set(config, '$.unet_fit', 'krea2_turbo-Q3_K_M.gguf')")
    details = ok(small_card.post(f"/api/images/backends/{backend['id']}/check"))['details']
    assert "krea2_turbo-Q3_K_M.gguf (about 7.6 GB) isn't in ComfyUI yet. It's the Krea 2 file that fits this 10 GB card. " \
        "Put it in ComfyUI's models/diffusion_models folder and add the ComfyUI-GGUF nodes, then press Check." in details
    assert not any('unet_name' in line for line in details)
    # Another family drops Krea 2's pick for one of its own, and a checkpoint family has none.
    ok(small_card.put(f"/api/images/backends/{backend['id']}", json={'family': 'zimage'}))
    assert saved_config(small_card, backend['id'])['unet_fit'] == 'z_image_turbo_int8_convrot.safetensors'
    ok(small_card.put(f"/api/images/backends/{backend['id']}", json={'family': 'booru'}))
    assert 'unet_fit' not in saved_config(small_card, backend['id'])


def test_other_families_sizes_come_from_their_real_files():
    # Comfy-Org's packages and unsloth's and Abiray's GGUF files, plus working room.
    assert 8 < hardware.image_size_gb('qwen_image_2.1_int8_convrot.safetensors') < 10
    assert 13 < hardware.image_size_gb('z_image_turbo_bf16.safetensors') < 14
    assert 5 < hardware.image_size_gb('anima-base-v1.0.safetensors') < 7
    assert hardware.image_size_gb('Qwen\\qwen-image-2.1-Q4_K_M.gguf') < hardware.image_size_gb('qwen-image-2.1-Q6_K.gguf')
    assert hardware.image_size_gb('z-image-turbo-Q3_K_M.gguf') < hardware.image_size_gb('z_image_turbo_nvfp4.safetensors') + 0.5
    assert hardware.image_size_gb('anima-base-v1.0-Q4_K_M.gguf') < 4
    # Animagine is an SDXL checkpoint, not Anima.
    assert hardware.image_size_gb('animagine-xl-4.0.safetensors') == 8.0


@pytest.mark.parametrize(('family', 'gpu', 'pick'), [
    ('qwen21', card('NVIDIA GeForce RTX 4060', 8.0), 'qwen_image_2.1_Q6_K.gguf'),
    ('qwen21', card('NVIDIA GeForce RTX 3050', 6.0), 'qwen_image_2.1_Q4_K_M.gguf'),
    ('qwen21', RTX_5070, None),
    ('zimage', RTX_5070, 'z_image_turbo_nvfp4.safetensors'),
    ('zimage', card('NVIDIA GeForce RTX 3080', 10.0), 'z_image_turbo_int8_convrot.safetensors'),
    ('zimage', card('NVIDIA GeForce RTX 3050', 6.0), 'z-image-turbo-Q3_K_M.gguf'),
    ('zimage', card('NVIDIA GeForce RTX 4080', 16.0), None),
    ('anima', card('NVIDIA GeForce GTX 1650', 4.0), 'anima-base-v1.0-Q6_K.gguf'),
    ('anima', card('NVIDIA GeForce RTX 4060', 8.0), None),
    # A checkpoint family has no smaller files to pick.
    ('booru', card('NVIDIA GeForce GTX 1650', 4.0), None)])
def test_every_family_with_smaller_files_gets_one_its_card_holds(family, gpu, pick):
    assert hardware.model_pick(gpu, family=family) == pick


def test_a_family_picks_only_its_own_files_for_its_workflow():
    have = ['krea2_turbo-Q3_K_M.gguf', 'qwen-image-2.1-turbo-Q6_K.gguf', 'Qwen\\qwen-image-2.1-Q5_K_M.gguf',
            'qwen_image_2.1_bf16.safetensors']
    # Not Krea 2's file, nor the Turbo one at 25 steps.
    assert hardware.model_pick(card('NVIDIA GeForce RTX 4060', 8.0), have, 'qwen21') == 'Qwen\\qwen-image-2.1-Q5_K_M.gguf'
    assert hardware.model_pick(card('NVIDIA GeForce GTX 1650', 4.0), ['anima-turbo-v1.0-Q8_0.gguf', 'anima-preview-Q5_K_M.gguf'],
                               'anima') == 'anima-preview-Q5_K_M.gguf'


def test_a_too_big_file_of_another_family_names_its_own_that_fits():
    image = {'id': 'b1', 'label': 'Local ComfyUI', 'base_url': 'http://127.0.0.1:8188',
             'unet': 'z_image_turbo_bf16.safetensors', 'size_gb': hardware.image_size_gb('z_image_turbo_bf16.safetensors'),
             'family': 'zimage'}
    listed = {image['base_url']: ['z-image-turbo-Q5_K_M.gguf']}
    found = hardware.check(computer(card('NVIDIA GeForce RTX 3060', 8.0)), [], [image], {}, listed)[0]
    assert found['action'] == {'label': 'Use z-image-turbo-Q5_K_M', 'backend_id': 'b1', 'unet_name': 'z-image-turbo-Q5_K_M.gguf'}
    assert hardware.missing_fit_line('qwen_image_2.1_Q6_K.gguf', card('NVIDIA GeForce RTX 4060', 8.0), 'qwen21') == (
        "qwen_image_2.1_Q6_K.gguf (about 7.8 GB) isn't in ComfyUI yet. It's the Qwen Image 2.1 file that fits this 8.0 GB "
        "card. Put it in ComfyUI's models/diffusion_models folder and add the ComfyUI-GGUF nodes, then press Check.")


@pytest.mark.parametrize('family', ['qwen21', 'zimage', 'anima'])
def test_another_familys_gguf_file_loads_through_the_gguf_loader(family):
    config = {'family': family, 'unet_fit': hardware.FITS[family].smaller[-1]}
    for workflow in (built_in(config), built_in(config, reference=True)):
        loaders = [node for node in workflow.values() if 'unet_name' in node['inputs']]
        assert loaders and all(node['class_type'] == 'UnetLoaderGGUF' for node in loaders)


def test_a_gguf_file_counts_only_where_the_gguf_loader_lists_it(monkeypatch):
    # Without the ComfyUI-GGUF nodes, a .gguf file on disk can't run, so no "Use" button offers it (Iris).
    def get(url, **kwargs):
        loader = url.rsplit('/', 1)[-1]
        names = {'UNETLoader': ['qwen_image_2.1_Q6_K.gguf', 'flux.safetensors']}.get(loader)
        spec = {loader: {'input': {'required': {'unet_name': [names, {}]}}}} if names else {}
        return httpx.Response(200 if names else 404, json=spec, request=httpx.Request('GET', url))
    monkeypatch.setattr(httpx, 'get', get)
    assert hardware.comfy_models('http://127.0.0.1:8188') == ['flux.safetensors']
