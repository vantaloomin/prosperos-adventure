"""A reasoning effort the model turns down is swapped for the nearest one it takes (dungeon/providers/efforts.py)."""
import asyncio
import json

import httpx
import pytest

from dungeon import text_models
from dungeon.errors import DomainError
from dungeon.providers import chat, efforts
from dungeon.providers.chat import ChatProvider

CONFIG = {'provider': 'openrouter', 'base_url': 'https://openrouter.ai/api/v1', 'model': 'luna', 'max_output_tokens': 100,
          'timeout_seconds': 10, 'reasoning_effort': 'minimal'}
OPENAI_SAID = ("Unsupported value: 'reasoning.effort' does not support 'minimal' with this model. "
               "Supported values are: 'none', 'low', 'medium', and 'high'.")


@pytest.fixture(autouse=True)
def fresh_models(monkeypatch):
    monkeypatch.setattr(chat, 'THINKS_PAST_THE_LIMIT', set())
    monkeypatch.setattr(efforts, 'REPLACED', {})


def reply(text='hey'):
    body = f'data: {json.dumps({"choices": [{"delta": {"content": text}, "finish_reason": "stop"}]})}\n\ndata: [DONE]\n\n'
    return httpx.Response(200, text=body, headers={'content-type': 'text/event-stream'})


def refused(said=OPENAI_SAID):
    return httpx.Response(400, json={'error': {'message': said, 'param': 'reasoning.effort'}})


def run(provider, *configs):
    async def go():
        return [''.join([chunk.text async for chunk in provider.stream(config, 'k', 'system', [{'role': 'user', 'content': 'hi'}])])
                for config in configs]
    return asyncio.run(go())


def test_reads_the_levels_the_service_names_and_picks_the_nearest():
    assert efforts.supported(OPENAI_SAID, 'minimal') == ['none', 'low', 'medium', 'high']
    assert efforts.nearest('minimal', ['none', 'low', 'medium', 'high']) == 'none'
    assert efforts.nearest('minimal', ['low', 'medium', 'high']) == 'low'
    assert efforts.nearest('max', ['low', 'medium', 'high']) == 'high'
    assert efforts.supported("reasoning.effort 'minimal' is not supported for this model.", 'minimal') is None
    assert efforts.nearest('minimal', None) is None


def test_only_a_refusal_about_the_effort_counts():
    assert efforts.turned_down(CONFIG, OPENAI_SAID)
    assert efforts.turned_down(CONFIG, 'Unrecognized request argument supplied: reasoning')
    assert not efforts.turned_down(CONFIG, 'max_tokens must be at most 4096')
    assert not efforts.turned_down({**CONFIG, 'reasoning_effort': None}, OPENAI_SAID)


def test_a_turned_down_effort_is_asked_again_with_the_nearest_one_and_remembered():
    bodies, answers = [], [refused(), reply('hi there'), reply('again')]
    learned = []

    def handler(request):
        bodies.append(json.loads(request.content))
        return answers.pop(0)

    provider = ChatProvider(httpx.MockTransport(handler))
    provider.learned_effort = lambda config, instead, levels: learned.append((config['reasoning_effort'], instead, levels))
    assert run(provider, CONFIG, CONFIG) == ['hi there', 'again']
    assert [body['reasoning'] for body in bodies] == [{'effort': 'minimal'}, {'effort': 'none'}, {'effort': 'none'}]
    assert learned == [('minimal', 'none', ['none', 'low', 'medium', 'high'])]


def test_with_no_levels_named_it_asks_without_an_effort():
    bodies, answers = [], [refused('This model does not support reasoning effort.'), reply()]

    def handler(request):
        bodies.append(json.loads(request.content))
        return answers.pop(0)

    assert run(ChatProvider(httpx.MockTransport(handler)), CONFIG) == ['hey']
    assert 'reasoning' not in bodies[1]


def test_other_refusals_still_fail_and_a_second_refusal_is_not_retried():
    with pytest.raises(DomainError, match='max_tokens'):
        run(ChatProvider(httpx.MockTransport(lambda request: refused('max_tokens must be at most 4096'))), CONFIG)
    calls = []

    def handler(request):
        calls.append(request)
        return refused()
    with pytest.raises(DomainError, match='turned down the request'):
        run(ChatProvider(httpx.MockTransport(handler)), CONFIG)
    assert len(calls) == 2


def test_the_profile_takes_the_replacement_and_offers_only_the_levels_the_model_takes(client, app):
    created = client.post('/api/models/profiles', json={'name': 'Luna', 'config': {
        'provider': 'openai', 'model': 'luna', 'reasoning_effort': 'minimal'}, 'api_key': 'k'}).json()
    config = {'profile_id': created['id'], 'model': 'luna', 'reasoning_effort': 'minimal'}
    text_models.learn_effort(app.state.database, config, 'none', ['none', 'low', 'medium', 'high'])
    profile = next(item for item in client.get('/api/models').json()['profiles'] if item['id'] == created['id'])
    assert profile['config']['reasoning_effort'] == 'none'
    assert profile['config']['reported_capabilities']['supported_efforts'] == ['none', 'low', 'medium', 'high']
    assert profile['revision'] == created['revision'] + 1
    # Saving it again from Settings passes the reported-levels check.
    saved = client.put(f'/api/models/profiles/{created["id"]}', json={
        'name': 'Luna', 'config': profile['config'], 'expected_revision': profile['revision']})
    assert saved.status_code == 200, saved.text
    # A profile the user changed in the meantime is left alone.
    text_models.learn_effort(app.state.database, config, 'low', ['low'])
    again = next(item for item in client.get('/api/models').json()['profiles'] if item['id'] == created['id'])
    assert again['config']['reasoning_effort'] == 'none'
