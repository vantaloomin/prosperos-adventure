import asyncio
import json

import httpx
import pytest

from dungeon.errors import DomainError
from dungeon.providers import chat
from dungeon.providers.chat import ChatProvider

CONFIG = {'base_url': 'http://127.0.0.1:1234/v1', 'model': 'm', 'max_output_tokens': 100, 'timeout_seconds': 10}


@pytest.fixture(autouse=True)
def fresh_models(monkeypatch):
    monkeypatch.setattr(chat, 'THINKS_PAST_THE_LIMIT', set())


def collect(provider, key=None):
    async def run():
        return [chunk async for chunk in provider.stream(CONFIG, key, 'system text', [{'role': 'user', 'content': 'hi'}])]
    return asyncio.run(run())


def test_streams_openai_compatible_events():
    seen = {}

    def handler(request):
        seen['body'] = json.loads(request.content)
        seen['auth'] = request.headers.get('authorization')
        events = [{'choices': [{'delta': {'content': 'Hel'}}]},
                  {'choices': [{'delta': {'content': 'lo'}, 'finish_reason': 'stop'}]}]
        body = ''.join(f'data: {json.dumps(event)}\n\n' for event in events) + 'data: [DONE]\n\n'
        return httpx.Response(200, text=body, headers={'content-type': 'text/event-stream'})

    chunks = collect(ChatProvider(httpx.MockTransport(handler)), 'k')
    assert ''.join(chunk.text for chunk in chunks) == 'Hello'
    assert chunks[-1].finish_reason == 'stop'
    assert seen['body']['messages'][0] == {'role': 'system', 'content': 'system text'}
    assert seen['auth'] == 'Bearer k'


def test_a_rate_limit_is_retried_once(monkeypatch):
    waits, answers = [], [httpx.Response(429, headers={'retry-after': '30'}),
                          httpx.Response(200, text='data: {"choices": [{"delta": {"content": "Hi"}, '
                                         '"finish_reason": "stop"}]}\n\n', headers={'content-type': 'text/event-stream'}),
                          httpx.Response(429), httpx.Response(429)]

    async def wait(seconds):
        waits.append(seconds)
    monkeypatch.setattr('dungeon.providers.chat.asyncio.sleep', wait)
    provider = ChatProvider(httpx.MockTransport(lambda request: answers.pop(0)))
    assert ''.join(chunk.text for chunk in collect(provider)) == 'Hi'
    assert waits == [5.0]
    with pytest.raises(DomainError, match='rate or usage limit'):
        collect(provider)
    assert waits == [5.0, 2.0] and answers == []


def test_authentication_failure_is_reported():
    provider = ChatProvider(httpx.MockTransport(lambda request: httpx.Response(401)))
    with pytest.raises(DomainError) as error:
        collect(provider)
    assert 'rejected the API key' in error.value.message


def test_unreachable_service_is_a_connection_error():
    def handler(request):
        raise httpx.ConnectError('refused')
    with pytest.raises(DomainError) as error:
        collect(ChatProvider(httpx.MockTransport(handler)))
    assert error.value.code == 'connection'


def sse(*events):
    body = ''.join(f'data: {json.dumps(event)}\n\n' for event in events) + 'data: [DONE]\n\n'
    return httpx.Response(200, text=body, headers={'content-type': 'text/event-stream'})


THOUGHT_ONLY = ({'choices': [{'delta': {'content': '', 'reasoning': 'Let me think about Sam...'}}]},
                {'choices': [{'delta': {}, 'finish_reason': 'length'}]},
                {'choices': [], 'usage': {'completion_tokens': 100,
                                          'completion_tokens_details': {'reasoning_tokens': 100}}})


def test_a_reply_spent_entirely_on_thinking_is_asked_again_with_less_thinking():
    bodies, answers = [], [sse(*THOUGHT_ONLY),
                           sse({'choices': [{'delta': {'content': 'hey!'}, 'finish_reason': 'stop'}]})]

    def handler(request):
        bodies.append(json.loads(request.content))
        return answers.pop(0)

    config = {**CONFIG, 'provider': 'openrouter', 'base_url': 'https://openrouter.ai/api/v1'}

    async def run():
        provider = ChatProvider(httpx.MockTransport(handler))
        return [chunk async for chunk in provider.stream(config, 'k', 'system', [{'role': 'user', 'content': 'hi'}])]
    chunks = asyncio.run(run())
    assert ''.join(chunk.text for chunk in chunks) == 'hey!'
    assert [chunk.finish_reason for chunk in chunks if chunk.finish_reason] == ['stop']
    assert 'reasoning' not in bodies[0] and bodies[0]['max_tokens'] == 100
    assert bodies[1]['reasoning'] == {'effort': 'low'} and bodies[1]['max_tokens'] == 200


def test_a_model_that_ran_out_while_thinking_is_asked_to_think_less_from_then_on():
    """A reply cut short after some text can't be asked again once shown, so the next one asks for low effort."""
    bodies = []

    def handler(request):
        bodies.append(json.loads(request.content))
        return sse({'choices': [{'delta': {'reasoning': 'hmm', 'content': 'so anyway'}, 'finish_reason': 'length'}]})

    config = {**CONFIG, 'provider': 'openrouter', 'base_url': 'https://openrouter.ai/api/v1'}

    async def run(*configs):
        provider = ChatProvider(httpx.MockTransport(handler))
        for each in configs:
            [chunk async for chunk in provider.stream(each, 'k', 'system', [{'role': 'user', 'content': 'hi'}])]
    asyncio.run(run(config, config, {**config, 'reasoning_effort': 'high'}))
    assert 'reasoning' not in bodies[0] and bodies[1]['reasoning'] == {'effort': 'low'}
    assert bodies[1]['max_tokens'] == bodies[0]['max_tokens']
    assert bodies[2]['reasoning'] == {'effort': 'high'}, "the user's own thinking setting wins"


def test_a_reply_cut_off_with_text_is_not_asked_again():
    calls = []

    def handler(request):
        calls.append(request)
        return sse({'choices': [{'delta': {'content': 'so anyway'}, 'finish_reason': 'length'}]})

    chunks = collect(ChatProvider(httpx.MockTransport(handler)))
    assert len(calls) == 1 and chunks[-1].finish_reason == 'length'


@pytest.mark.parametrize('status,body,expected', [
    (404, {'detail': 'Function not found for account'}, 'did not recognize the model "m"'),
    (400, {'error': {'message': 'max_tokens must be at most 4096'}}, 'turned down the request (HTTP 400)'),
    (503, {'message': 'Model is overloaded'}, 'a problem on its side (HTTP 503)'),
    # NVIDIA NIM's answer for a retired model, as it gives it.
    (410, {'type': 'about:blank', 'title': 'Gone', 'status': 410,
           'detail': "The model 'm' has reached its end of life and is no longer available."}, 'no longer offers the model "m"'),
])
def test_a_failed_reply_says_what_the_service_answered(status, body, expected):
    """A tester on NVIDIA NIM saw only "The reply failed unexpectedly"; the service's own reason is now quoted."""
    provider = ChatProvider(httpx.MockTransport(lambda request: httpx.Response(status, json=body)))
    with pytest.raises(DomainError) as error:
        collect(provider)
    said = body.get('detail') or body.get('message') or body['error']['message']
    assert expected in error.value.message and f'It said: "{said}"' in error.value.message
