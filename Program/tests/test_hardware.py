from dungeon import hardware
from dungeon.hardware import Hardware


def card(index, name, memory):
    return {'index': index, 'name': name, 'memory_gb': memory, 'usable_gb': memory, 'used_gb': None, 'shared': False}


def computer(*gpus, memory=64):
    return {'system': 'Windows', 'cores': 16, 'memory_gb': memory, 'gpus': list(gpus), 'gpu_note': None}


GEMMA = {'profile': 'Kobold', 'model': 'koboldcpp/gemma-4-31b-it-Q4_K_M',
         'size_gb': hardware.text_size_gb('gemma-4-31b-it-Q4_K_M')}
KREA = {'label': 'Local ComfyUI', 'base_url': 'http://127.0.0.1:8188', 'unet': 'krea2_turbo_fp8_scaled.safetensors',
        'size_gb': hardware.image_size_gb('krea2_turbo_fp8_scaled.safetensors'), 'family': 'krea2'}


def test_reads_nvidia_smi_output():
    gpus = hardware.nvidia_gpus('0, NVIDIA GeForce RTX 5090, 32607, 21000\n1, NVIDIA GeForce RTX 4090, 24564, [N/A]\n')
    assert [(gpu['index'], gpu['name'], round(gpu['memory_gb'])) for gpu in gpus] == \
        [(0, 'NVIDIA GeForce RTX 5090', 32), (1, 'NVIDIA GeForce RTX 4090', 24)]
    assert round(gpus[0]['used_gb']) == 21 and gpus[1]['used_gb'] is None
    assert hardware.nvidia_gpus('garbage\n') == []


def test_estimates_text_model_size_from_its_name():
    assert hardware.text_size_gb('gemma4:31b') == hardware.text_size_gb('gemma-4-31b-it-Q4_K_M')
    assert 20 < hardware.text_size_gb('gemma-4-31b-it-Q4_K_M') < 24
    assert hardware.text_size_gb('qwen3-30b-a3b-Q8_0') > hardware.text_size_gb('qwen3-30b-a3b-Q4_K_M')
    assert hardware.text_size_gb('Mixtral-8x7B-Instruct.Q4_K_M') > hardware.text_size_gb('mistral-7b-instruct.Q4_K_M')
    assert hardware.text_size_gb('local-model') is None
    assert hardware.image_size_gb('krea2_turbo_fp8_scaled.safetensors') > hardware.image_size_gb('krea2_nvfp4.safetensors')


def test_what_a_computer_can_run():
    lines = hardware.can_run(computer(card(0, 'RTX 4060', 8)))
    assert 'about 8B' in lines[0] and 'hosted image service' in lines[1]
    two = hardware.can_run(computer(card(0, 'RTX 5090', 32), card(1, 'RTX 4090', 24)))
    assert '--cuda-device 1' in two[1]
    assert 'processor' in hardware.can_run(computer())[0]


def test_warns_when_text_and_pictures_cannot_share_one_card():
    warnings = hardware.check(computer(card(0, 'RTX 4090', 24)), [GEMMA], [KREA], {})
    assert [warning['area'] for warning in warnings] == ['images']
    assert "don't both fit" in warnings[0]['text'] and 'about 12B' in warnings[0]['text']
    assert hardware.check(computer(card(0, 'RTX 6000', 48)), [GEMMA], [KREA], {}) == []


def test_warns_about_a_text_model_too_big_for_the_card():
    warnings = hardware.check(computer(card(0, 'RTX 4060', 8)), [GEMMA], [], {})
    assert warnings[0]['tone'] == 'warning' and 'replies will be slow' in warnings[0]['text']
    assert 'may not load' in hardware.check(computer(card(0, 'RTX 4060', 8), memory=8), [GEMMA], [], {})[-1]['text']


def test_two_cards_point_comfyui_at_the_other_one():
    gpus = (card(0, 'RTX 5090', 32), card(1, 'RTX 4090', 24))
    unknown = hardware.check(computer(*gpus), [GEMMA], [KREA], {})
    assert unknown[0]['tone'] == 'tip' and '--cuda-device 1' in unknown[0]['text']
    same = hardware.check(computer(*gpus), [GEMMA], [KREA], {KREA['base_url']: 'cuda:0 NVIDIA GeForce RTX 5090 : x'})
    assert same[0]['tone'] == 'warning'
    assert hardware.check(computer(*gpus), [GEMMA], [KREA], {KREA['base_url']: 'cuda:1 NVIDIA GeForce RTX 4090 : x'}) == []


def test_report_checks_the_models_in_use(app, client):
    app.state.hardware = Hardware(scanner=lambda: computer(card(0, 'RTX 4090', 24)), device=lambda url: None)
    empty = client.get('/api/hardware').json()
    assert empty['warnings'] == [] and empty['can_run']
    response = client.post('/api/models/profiles', json={'name': 'Kobold', 'config': {
        'provider': 'kobold', 'model': 'koboldcpp/gemma-4-31b-it-Q4_K_M'}})
    assert response.status_code == 201, response.text
    response = client.post('/api/images/backends', json={'kind': 'comfyui', 'base_url': 'http://127.0.0.1:8188',
                                                         'accept_disclosure': True})
    assert response.status_code == 200, response.text
    report = client.get('/api/hardware?fresh=true').json()
    assert [text['model'] for text in report['local_text']] == ['koboldcpp/gemma-4-31b-it-Q4_K_M']
    assert report['local_images'][0]['unet'] == 'krea2_turbo_fp8_scaled.safetensors'
    assert [warning['area'] for warning in report['warnings']] == ['images']
