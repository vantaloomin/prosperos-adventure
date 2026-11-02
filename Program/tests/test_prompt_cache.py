"""Instant replies on local models (dungeon/providers/prompt_cache.py): prompt starts kept and put back."""
import asyncio
import json

import httpx

from dungeon.providers.chat import ChatProvider

CONFIG = {'base_url': 'http://127.0.0.1:8080/v1', 'model': 'gemma', 'max_output_tokens': 100, 'timeout_seconds': 10,
          'provider': 'local'}
MIRA = 'You are Mira. ' + 'Warm and curious. ' * 200 + '\n## What you know about the user\n- Name: Sam'
SALLY = 'You are Sally. ' + 'Dry and quick. ' * 200 + '\n## What you know about the user\n- Name: Sam'


def llama(calls: list, slots=True):
    """A llama.cpp server: /props, slot save and restore, and a streamed reply."""
    def handler(request):
        path = request.url.path
        if path == '/props':
            return httpx.Response(200, json={'total_slots': 1})
        if path.startswith('/slots/'):
            calls.append((request.url.params['action'], json.loads(request.content)['filename']))
            return httpx.Response(200 if slots else 501, json={})
        calls.append(('reply', json.loads(request.content).get('id_slot')))
        body = 'data: ' + json.dumps({'choices': [{'delta': {'content': 'Hi'}, 'finish_reason': 'stop'}]}) + '\n\n'
        return httpx.Response(200, text=body + 'data: [DONE]\n\n', headers={'content-type': 'text/event-stream'})
    return httpx.MockTransport(handler)


def reply(provider, system):
    async def run():
        return [chunk async for chunk in provider.stream(CONFIG, None, system, [{'role': 'user', 'content': 'hi'}])]
    return asyncio.run(run())


def test_switching_companions_saves_one_and_loads_the_other():
    calls = []
    provider = ChatProvider(llama(calls))
    reply(provider, MIRA)
    reply(provider, MIRA)  # The same companion again: nothing is saved or loaded.
    assert calls == [('reply', 0), ('reply', 0)]
    reply(provider, SALLY)
    saved_mira = calls[2]
    assert saved_mira[0] == 'save' and calls[3] == ('reply', 0)
    reply(provider, MIRA)
    assert calls[4][0] == 'save' and calls[5] == ('restore', saved_mira[1]) and calls[6] == ('reply', 0)


def test_a_short_background_prompt_still_keeps_the_chat():
    calls = []
    provider = ChatProvider(llama(calls))
    reply(provider, MIRA)
    reply(provider, 'Summarize this.')
    assert calls[1][0] == 'save' and calls[2] == ('reply', None)
    reply(provider, MIRA)
    assert calls[3][0] == 'restore'


def test_a_server_that_cannot_save_is_left_alone():
    calls = []
    provider = ChatProvider(llama(calls, slots=False))
    reply(provider, MIRA)
    reply(provider, SALLY)
    reply(provider, MIRA)
    assert [call for call in calls if call[0] != 'reply'] == [('save', calls[1][1])]
    assert calls[-1] == ('reply', None)


def test_a_server_that_was_not_up_yet_is_asked_again(monkeypatch):
    from dungeon.providers import prompt_cache
    calls, up = [], {'yes': False}
    serving = llama(calls)

    def handler(request):
        if not up['yes'] and request.url.path == '/props':
            raise httpx.ConnectError('refused', request=request)
        return serving.handle_request(request)
    provider = ChatProvider(httpx.MockTransport(handler))
    reply(provider, MIRA)
    assert calls == [('reply', None)]
    up['yes'] = True
    monkeypatch.setattr(prompt_cache, 'REPROBE_SECONDS', 0)
    reply(provider, MIRA)
    assert calls[-1] == ('reply', 0)
