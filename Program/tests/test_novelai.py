"""NovelAI's own image API as a hosted provider."""
import asyncio
import io
import json
import zipfile

import httpx
import pytest

from dungeon.images import tags
from dungeon.images.adapters import novelai
from dungeon.images.adapters.base import AdapterError, ImageRequest
from dungeon.images.adapters.hosted import HostedAdapter
from tests.test_images import add_backend, ok, png

TOKEN = 'pst-test-token'


def zipped(*names) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        for name in names:
            archive.writestr(name, png())
    return buffer.getvalue()


def server(responses, seen):
    def handler(request: httpx.Request):
        seen.append(request)
        return responses.pop(0)
    return httpx.MockTransport(handler)


def request(model='nai-diffusion-4-5-full', **values) -> ImageRequest:
    base = {'job_id': 'job1', 'prompt': 'Anime illustration.\nMira reads in a café. She is the only person in the '
            'picture.', 'negative': 'text', 'seed': 2**40 + 5, 'width': 1024, 'height': 1536,
            'backend': {'kind': 'hosted', 'provider': 'novelai'},
            'config': {'base_url': novelai.BASE_URL, 'model': model, 'api_style': 'novelai'}, 'key': TOKEN}
    return ImageRequest(**{**base, **values})


@pytest.mark.parametrize(('model', 'version'), [('nai-diffusion-4-5-full', 3), ('nai-diffusion-4-full', 3),
                                                 ('nai-diffusion-5-full', 4), ('nai-diffusion-3', None)])
def test_each_model_family_gets_its_own_request_shape(model, version):
    body = novelai.body(model, 'solo, 1girl', 'lowres', 2**40 + 5, 1024, 1536)
    parameters = body['parameters']
    assert body['input'] == 'solo, 1girl' and body['model'] == model and body['action'] == 'generate'
    assert parameters.get('params_version') == version
    # The free size of the same shape, at 28 steps, one picture, with a 32-bit seed.
    assert (parameters['width'], parameters['height'], parameters['steps'], parameters['n_samples']) == (832, 1216, 28, 1)
    assert parameters['seed'] == 5
    if version:
        assert parameters['v4_prompt']['caption']['base_caption'] == 'solo, 1girl'
        assert parameters['v4_negative_prompt']['caption']['base_caption'] == 'lowres'
    else:
        assert 'v4_prompt' not in parameters


def test_sizes_keep_their_shape():
    assert novelai.fit(1536, 1024) == (1216, 832) and novelai.fit(1024, 1024) == (1024, 1024)


def test_a_picture_comes_out_of_the_zip_with_tag_prompts():
    seen = []
    adapter = HostedAdapter(server([httpx.Response(200, content=zipped('image_0.png'))], seen))
    result = asyncio.run(adapter.generate(request()))
    sent = json.loads(seen[0].content)
    assert seen[0].url == httpx.URL(novelai.BASE_URL + '/ai/generate-image')
    assert seen[0].headers['authorization'] == f'Bearer {TOKEN}'
    assert result.data.startswith(b'\x89PNG') and result.model == 'nai-diffusion-4-5-full' and result.seed == 5
    # Booru tags, not the paragraph: one person drawn alone.
    assert sent['input'].startswith(tags.ILLUSTRIOUS) and 'solo, 1girl' in sent['input']
    assert 'only person' not in sent['input'] and '1boy' in sent['parameters']['negative_prompt']


def test_a_busy_account_is_waited_out(monkeypatch):
    monkeypatch.setattr(novelai, 'MAX_WAIT', 0.0)
    seen = []
    adapter = HostedAdapter(server([httpx.Response(429, headers={'retry-after': '1'}),
                                    httpx.Response(200, content=zipped('a.png'))], seen))
    assert asyncio.run(adapter.generate(request())).data.startswith(b'\x89PNG') and len(seen) == 2


@pytest.mark.parametrize(('response', 'code'), [
    (httpx.Response(401, json={'message': 'Unauthorized'}), 'auth'),
    (httpx.Response(402, json={'message': 'Not enough Anlas'}), 'failed'),
    (httpx.Response(400, json={'message': 'bad width'}), 'failed'),
    (httpx.Response(200, content=b'not a zip'), 'invalid_output'),
    (httpx.Response(200, content=zipped('notes.txt')), 'invalid_output'),
])
def test_failures_are_typed(response, code):
    with pytest.raises(AdapterError) as error:
        asyncio.run(HostedAdapter(server([response], [])).generate(request()))
    assert error.value.code == code


def test_a_missing_token_is_named():
    with pytest.raises(AdapterError) as error:
        asyncio.run(HostedAdapter(server([], [])).generate(request(key=None)))
    assert error.value.code == 'auth' and 'NovelAI API token under Connection' in error.value.message


def test_no_reference_picture_is_sent():
    with pytest.raises(AdapterError) as error:
        asyncio.run(HostedAdapter(server([], [])).generate(request(reference=png())))
    assert error.value.code == 'incompatible'


@pytest.mark.parametrize(('account', 'passed', 'words'), [
    ({'tier': 3, 'active': True}, True, 'free'),
    ({'tier': 1, 'active': True}, True, 'Anlas'),
    ({'tier': 0, 'active': False}, False, 'no active subscription'),
])
def test_check_reads_the_plan_and_spends_nothing(account, passed, words):
    seen = []
    adapter = HostedAdapter(server([httpx.Response(200, json=account)], seen))
    report = asyncio.run(adapter.check({'provider': 'novelai'}, {'base_url': novelai.BASE_URL,
                                                                 'model': 'nai-diffusion-4-5-full'}, TOKEN))
    assert seen[0].method == 'GET' and seen[0].url.path == '/user/subscription'
    assert report.ok is passed and any(words in line for line in [report.summary, *report.details])


def test_check_needs_the_token():
    report = asyncio.run(HostedAdapter(server([], [])).check({'provider': 'novelai'}, {'base_url': novelai.BASE_URL}))
    assert not report.ok and 'token' in report.summary


def test_the_models_are_known_without_a_request():
    models = asyncio.run(HostedAdapter(server([], [])).models('novelai', {'base_url': novelai.BASE_URL}))
    assert 'nai-diffusion-4-5-full' in {model['id'] for model in models}


def test_a_novelai_backend_runs_one_at_a_time_and_may_take_nsfw(client):
    backend = add_backend(client, kind='hosted', provider='novelai', model='nai-diffusion-4-5-full', api_key=TOKEN,
                          allows_nsfw=True, concurrency=3)
    assert backend['label'] == 'NovelAI' and backend['base_url'] == novelai.BASE_URL
    assert backend['concurrency'] == 1 and backend['accepts_nsfw'] and not backend['takes_reference']
    assert 'only the prompt is sent' in backend['disclosure'] and 'profile picture' not in backend['disclosure']
    assert backend['tag_prompts']
    assert backend['family_style'] == tags.ILLUSTRIOUS and backend['style'] == ''
    listed = ok(client.post('/api/images/models', json={'provider': 'novelai'}))
    assert listed['ok'] and listed['models'] == novelai.MODELS
