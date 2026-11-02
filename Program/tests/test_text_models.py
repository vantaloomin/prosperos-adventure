"""Settings > Models: profiles per provider, the connection test, job assignments and the move
from the single connection that came before profiles."""
import asyncio
import json

import httpx
import pytest

from dungeon import text_models
from dungeon.errors import DomainError
from dungeon.providers.chat import ChatProvider
from dungeon.providers.requests import CACHED, REQUESTS, headers_for, transcript

LOCAL = {'provider': 'local', 'model': 'local-model'}
ANTHROPIC = {'provider': 'anthropic', 'model': 'claude-sonnet-5-5', 'max_output_tokens': 1000}


def add(client, config, name='', api_key=None, status=201):
    response = client.post('/api/models/profiles', json={'name': name, 'config': config, 'api_key': api_key})
    assert response.status_code == status, response.text
    return response.json()


RECALL = {'provider': 'local', 'base_url': 'http://127.0.0.1:11434/v1', 'purpose': 'recall',
          'embedding_model': 'qwen3-embedding'}


def claude_key(app, claude):
    with app.state.database.connect() as connection:
        return connection.execute('SELECT credential_ref FROM model_profiles WHERE id=?', (claude['id'],)).fetchone()[0]


def test_official_addresses_and_adapter_limits_are_enforced(client):
    add(client, {**ANTHROPIC, 'base_url': 'https://example.com/v1'}, status=422)
    add(client, {**ANTHROPIC, 'temperature': 1.5}, status=422)
    add(client, {**LOCAL, 'base_url': 'http://192.168.1.20:1234/v1'}, status=422)
    add(client, {'provider': 'openai', 'model': 'gpt', 'top_k': 5}, status=422)
    add(client, {'provider': 'codex', 'model': 'gpt-5'}, api_key='nope', status=422)
    add(client, {'provider': 'claude_code', 'model': 'sonnet'}, api_key='nope', status=422)
    plan = add(client, {'provider': 'claude_code', 'model': 'sonnet'})
    assert plan['ready'] and plan['provider_name'] == 'Claude Code / Claude plan' and not plan['has_saved_key']
    official = add(client, {'provider': 'openai', 'model': 'gpt'})
    assert official['config']['base_url'] == 'https://api.openai.com/v1'


def test_a_saved_key_never_follows_a_changed_address(client, app):
    vault = app.state.vault
    profile = add(client, {'provider': 'compatible', 'model': 'm', 'base_url': 'https://one.example/v1'}, api_key='k1')
    reference = next(iter(vault.secrets))
    same = client.put(f"/api/models/profiles/{profile['id']}", json={
        'name': 'Renamed', 'config': {'provider': 'compatible', 'model': 'm2', 'base_url': 'https://one.example/v1'},
        'expected_revision': profile['revision']}).json()
    assert same['has_saved_key'] and same['name'] == 'Renamed' and vault.secrets == {reference: 'k1'}
    moved = client.put(f"/api/models/profiles/{profile['id']}", json={
        'config': {'provider': 'compatible', 'model': 'm2', 'base_url': 'https://two.example/v1'},
        'expected_revision': same['revision']}).json()
    assert not moved['has_saved_key'] and vault.secrets == {}
    stale = client.put(f"/api/models/profiles/{profile['id']}", json={
        'config': {'provider': 'compatible', 'model': 'm3', 'base_url': 'https://two.example/v1'},
        'expected_revision': same['revision']})
    assert stale.status_code == 409


def test_deleting_a_profile_removes_its_key_and_jobs(client, app):
    local = add(client, LOCAL)
    claude = add(client, ANTHROPIC, api_key='sk-ant')
    client.put('/api/models/routes', json={'job': 'story', 'profile_id': claude['id']})
    result = client.delete(f"/api/models/profiles/{claude['id']}").json()
    assert result['routes'] == {'chat': local['id']} and app.state.vault.secrets == {}


def test_a_profile_doing_a_job_must_keep_a_model(client):
    local = add(client, LOCAL)
    response = client.put(f"/api/models/profiles/{local['id']}", json={
        'config': {'provider': 'local', 'model': ''}, 'expected_revision': local['revision']})
    assert response.status_code == 409


def test_the_narrator_mix_takes_turns_and_falls_back_to_the_job_profile(client, app):
    one = add(client, LOCAL, name='One')
    two = add(client, {**LOCAL, 'model': 'other-model'}, name='Two')
    database = app.state.database
    with database.connect(write=True) as connection:
        assert text_models.reply_config(connection, 'story')['profile_id'] == one['id']
    assert client.put('/api/models/mix', json={'job': 'chat', 'profile_ids': [one['id']]}).status_code == 422
    result = client.put('/api/models/mix', json={'profile_ids': [one['id'], two['id']], 'mode': 'in_turn'}).json()
    assert result['mix']['story'] == {'enabled': True, 'mode': 'in_turn', 'profile_ids': [one['id'], two['id']]}
    with database.connect(write=True) as connection:
        turns = [text_models.reply_config(connection, 'story')['profile_id'] for _ in range(3)]
        assert turns == [one['id'], two['id'], one['id']]
        assert text_models.reply_config(connection, 'chat')['profile_id'] == one['id']
    client.put('/api/models/mix', json={'profile_ids': [one['id'], two['id']], 'mode': 'random'})
    with database.connect(write=True) as connection:
        picked = text_models.reply_config(connection, 'story', chooser=lambda rows: rows[-1])
        assert picked['profile_id'] == two['id'] and picked['model'] == 'other-model'
    # A profile in the Mix must keep its model; deleting it leaves one, which is no mix at all.
    response = client.put(f"/api/models/profiles/{two['id']}", json={
        'config': {'provider': 'local', 'model': ''}, 'expected_revision': two['revision']})
    assert response.status_code == 409
    result = client.delete(f"/api/models/profiles/{two['id']}").json()
    assert result['mix']['story']['profile_ids'] == [one['id']]
    with database.connect(write=True) as connection:
        assert text_models.reply_config(connection, 'story', chooser=lambda rows: 1 / 0)['profile_id'] == one['id']
    off = client.put('/api/models/mix', json={'profile_ids': [one['id']], 'enabled': False}).json()
    assert off['mix']['story']['enabled'] is False


# --- Provider adapters ----------------------------------------------------------------------------

CONVERSATION = [{'role': 'assistant', 'content': 'Morning!'}, {'role': 'user', 'content': 'Hi'},
                {'role': 'user', 'content': 'Still there?'}]


def config(provider, **extra):
    return {'provider': provider, 'model': 'm', 'base_url': 'https://x.example/v1', 'max_output_tokens': 300,
            'context_tokens': 4000, 'timeout_seconds': 10, **extra}


def test_claude_caches_the_system_prompt_and_the_conversation_before_the_latest_message():
    _path, body = REQUESTS['anthropic'](config('anthropic'), 'sys', CONVERSATION)
    assert body['messages'][1] == {'role': 'assistant', 'content': [{'type': 'text', 'text': 'Morning!',
                                                                     'cache_control': CACHED}]}
    assert 'cache_control' not in str(body['messages'][2]) and 'cache_control' not in str(body['messages'][0])
    _path, body = REQUESTS['openrouter'](config('openrouter', model='anthropic/claude-sonnet-5.5'), 'sys', CONVERSATION)
    assert body['messages'][0]['content'] == [{'type': 'text', 'text': 'sys', 'cache_control': CACHED}]
    assert body['messages'][2]['content'] == [{'type': 'text', 'text': 'Hi', 'cache_control': CACHED}]
    assert body['messages'][3] == {'role': 'user', 'content': 'Still there?'}
    # Other models cache on their own, and a plain request suits every server.
    for provider, model in [('openrouter', 'google/gemma-4-31b-it'), ('local', 'qwen3.6-27b')]:
        _path, body = REQUESTS[provider](config(provider, model=model), 'sys', CONVERSATION)
        assert 'cache_control' not in str(body) and body['messages'][0] == {'role': 'system', 'content': 'sys'}


def test_anthropic_and_gemini_get_alternating_turns_that_open_with_the_user():
    path, body = REQUESTS['anthropic'](config('anthropic', thinking_mode='adaptive'), 'sys', CONVERSATION)
    assert path == '/messages' and body['system'] == [{'type': 'text', 'text': 'sys', 'cache_control': CACHED}]
    assert [message['role'] for message in body['messages']] == ['user', 'assistant', 'user']
    assert body['messages'][-1]['content'] == 'Hi\n\nStill there?'
    assert body['thinking'] == {'type': 'adaptive'}
    path, body = REQUESTS['google'](config('google', model='models/gemini-3'), 'sys', CONVERSATION)
    assert path == '/models/gemini-3:streamGenerateContent?alt=sse'
    assert [content['role'] for content in body['contents']] == ['user', 'model', 'user']
    assert headers_for(config('anthropic'), 'k')['x-api-key'] == 'k'
    assert headers_for(config('google'), 'k')['x-goog-api-key'] == 'k'


def test_openai_uses_responses_and_compatible_services_use_chat_completions():
    path, body = REQUESTS['openai'](config('openai', reasoning_effort='low'), 'sys', CONVERSATION)
    assert path == '/responses' and body['instructions'] == 'sys' and body['store'] is False
    assert body['input'][0] == {'role': 'assistant', 'content': 'Morning!'} and body['reasoning'] == {'effort': 'low'}
    path, body = REQUESTS['compatible'](config('compatible', output_token_parameter='max_completion_tokens'), 'sys',
                                        CONVERSATION)
    assert path == '/chat/completions' and body['max_completion_tokens'] == 300
    assert body['messages'][0] == {'role': 'system', 'content': 'sys'}
    path, body = REQUESTS['openrouter'](config('openrouter'), 'sys', CONVERSATION)
    assert body['provider'] == {'allow_fallbacks': False, 'require_parameters': True}
    path, body = REQUESTS['kobold'](config('kobold'), 'sys', CONVERSATION)
    assert body['prompt'] == transcript('sys', CONVERSATION) and body['prompt'].endswith('Assistant:')
    path, body = REQUESTS['nanogpt'](config('nanogpt'), 'sys', CONVERSATION)
    assert path == '/chat/completions' and 'provider' not in body and body['stream_options'] == {'include_usage': True}


def test_nanogpt_is_a_named_provider_with_its_official_address():
    from dungeon.providers.config import DEFAULT_URLS, NEEDS_KEY, validate_profile_url
    assert DEFAULT_URLS['nanogpt'] == 'https://nano-gpt.com/api/v1' and 'nanogpt' in NEEDS_KEY
    validate_profile_url('nanogpt', 'https://nano-gpt.com/api/v1')
    with pytest.raises(ValueError):
        validate_profile_url('nanogpt', 'https://elsewhere.example/v1')


def sse(events):
    return ''.join(f'data: {json.dumps(event)}\n\n' for event in events)


def collect(provider, settings, key='k'):
    async def run():
        return [chunk async for chunk in provider.stream(settings, key, 'sys', [{'role': 'user', 'content': 'hi'}])]
    return asyncio.run(run())


def test_anthropic_stream_is_read_to_its_stop_reason():
    seen = {}

    def handler(request):
        seen['url'] = str(request.url)
        return httpx.Response(200, text=sse([
            {'type': 'message_start', 'message': {'usage': {'input_tokens': 3}}},
            {'type': 'content_block_delta', 'delta': {'type': 'text_delta', 'text': 'Hel'}},
            {'type': 'content_block_delta', 'delta': {'type': 'text_delta', 'text': 'lo'}},
            {'type': 'message_delta', 'delta': {'stop_reason': 'max_tokens'}},
            {'type': 'message_stop'}]))
    settings = {**config('anthropic'), 'base_url': 'https://api.anthropic.com/v1'}
    chunks = collect(ChatProvider(httpx.MockTransport(handler)), settings)
    assert ''.join(chunk.text for chunk in chunks) == 'Hello' and chunks[-1].finish_reason == 'length'
    assert seen['url'] == 'https://api.anthropic.com/v1/messages'


def test_a_stream_that_never_finishes_is_an_error():
    transport = httpx.MockTransport(lambda request: httpx.Response(200, text=sse([
        {'choices': [{'delta': {'content': 'Hel'}}]}])))
    with pytest.raises(DomainError) as error:
        collect(ChatProvider(transport), config('compatible'))
    assert 'ended before' in error.value.message


def test_hosted_providers_need_a_key():
    with pytest.raises(DomainError) as error:
        collect(ChatProvider(httpx.MockTransport(lambda request: httpx.Response(500))), config('openrouter'), key=None)
    assert error.value.status == 409


def test_duplicating_a_profile_copies_its_settings_and_key_but_not_its_jobs(client, app):
    local = add(client, LOCAL)
    claude = add(client, {**ANTHROPIC, 'temperature': 0.4}, name='Claude', api_key='sk-ant')
    client.put('/api/models/routes', json={'job': 'story', 'profile_id': claude['id']})
    copy = client.post(f"/api/models/profiles/{claude['id']}/duplicate")
    assert copy.status_code == 201
    copy = copy.json()
    assert copy['name'] == 'Claude copy' and copy['config'] == claude['config'] and copy['has_saved_key']
    assert client.post(f"/api/models/profiles/{claude['id']}/duplicate").json()['name'] == 'Claude copy 2'
    assert client.get('/api/models').json()['routes'] == {'chat': local['id'], 'story': claude['id']}
    # A new key on the copy asked to be its own leaves the original's alone; deleting one keeps the other's key.
    client.put(f"/api/models/profiles/{copy['id']}", json={'name': 'Claude copy', 'config': copy['config'],
                                                          'api_key': 'sk-other', 'share_key': False,
                                                          'expected_revision': 1})
    client.delete(f"/api/models/profiles/{copy['id']}")
    with app.state.database.connect() as connection:
        assert text_models.key_for(app.state.vault, text_models.config_for(connection, 'story')) == 'sk-ant'


def test_a_json_schema_is_enforced_in_each_apis_own_way():
    shape = {'type': 'object', 'properties': {'facts': {'type': 'array'}}}
    _path, body = REQUESTS['openai'](config('openai', json_schema=shape), 'sys', CONVERSATION)
    assert body['text']['format'] == {'type': 'json_schema', 'name': 'answer', 'schema': shape, 'strict': True}
    _path, body = REQUESTS['anthropic'](config('anthropic', json_schema=shape, reasoning_effort='low'), 'sys',
                                        CONVERSATION)
    assert body['output_config'] == {'effort': 'low', 'format': {'type': 'json_schema', 'schema': shape}}
    _path, body = REQUESTS['google'](config('google', model='gemini-3', json_schema=shape), 'sys', CONVERSATION)
    assert body['generationConfig']['responseJsonSchema'] == shape
    for provider in ('openrouter', 'local', 'compatible', 'nanogpt'):
        _path, body = REQUESTS[provider](config(provider, json_schema=shape), 'sys', CONVERSATION)
        assert body['response_format']['json_schema']['schema'] == shape
    _path, body = REQUESTS['kobold'](config('kobold', json_schema=shape), 'sys', CONVERSATION)
    assert 'response_format' not in body
    # Without a schema nothing changes.
    _path, body = REQUESTS['local'](config('local'), 'sys', CONVERSATION)
    assert 'response_format' not in body


def test_a_new_profile_on_the_same_service_reuses_its_saved_key(client, app):
    """A tester's OpenAI key for chat had to be pasted again for recall; one saved key now does both."""
    chat = add(client, {'provider': 'openai', 'model': 'gpt-5'}, api_key='sk-openai')
    recall = add(client, {'provider': 'openai', 'purpose': 'recall', 'model': '', 'embedding_model': 'text-embedding-3-small'})
    second = add(client, {'provider': 'openai', 'model': 'gpt-5-mini'})
    other = add(client, {'provider': 'openrouter', 'model': 'x/y'})
    elsewhere = add(client, {'provider': 'compatible', 'model': 'm', 'base_url': 'https://one.example/v1'})
    assert recall['has_saved_key'] and second['has_saved_key']
    assert not other['has_saved_key'] and not elsewhere['has_saved_key']
    assert list(app.state.vault.secrets.values()) == ['sk-openai']
    with app.state.database.connect() as connection:
        assert text_models.key_for(app.state.vault, text_models.config_for(connection, 'recall')) == 'sk-openai'
    shared = {item['id']: item['key_shared_with'] for item in client.get('/api/models').json()['profiles']}
    assert set(shared[chat['id']]) == {recall['name'], second['name']}
    assert chat['name'] in shared[recall['id']] and shared[other['id']] == []
    # Deleting the profile the key was typed into keeps it for the others.
    client.delete(f"/api/models/profiles/{chat['id']}")
    assert list(app.state.vault.secrets.values()) == ['sk-openai']


def test_a_keyless_profile_picks_up_a_key_saved_later_for_its_service(client, app):
    first = add(client, {'provider': 'openrouter', 'model': 'a/b'})
    add(client, {'provider': 'openrouter', 'model': 'c/d'}, api_key='or-key')
    saved = client.put(f"/api/models/profiles/{first['id']}", json={
        'name': first['name'], 'config': first['config'], 'expected_revision': first['revision']}).json()
    assert saved['has_saved_key']


def test_testing_a_new_form_uses_the_key_saved_for_its_service(client, app):
    add(client, {'provider': 'openrouter', 'model': 'a/b'}, api_key='or-key')
    body = type('Probe', (), {'api_key': None, 'profile_id': None,
                              'config': type('Config', (), {'model_dump': lambda self: {
                                  'provider': 'openrouter', 'base_url': 'https://openrouter.ai/api/v1'}})()})()
    assert text_models.probe_key(app.state.database, app.state.vault, body) == 'or-key'


def test_a_new_key_on_a_shared_profile_replaces_it_for_every_profile_sharing_it(client, app):
    """A rotated key (OpenRouter keys expire) must keep recall and every other job on that service working."""
    chat = add(client, {'provider': 'openai', 'model': 'gpt-5'}, api_key='old')
    recall = add(client, {'provider': 'openai', 'purpose': 'recall', 'model': '', 'embedding_model': 'e'})
    saved = client.put(f"/api/models/profiles/{chat['id']}", json={
        'name': chat['name'], 'config': chat['config'], 'api_key': 'new', 'expected_revision': chat['revision']}).json()
    assert saved['key_shared_with'] == [recall['name']]
    assert list(app.state.vault.secrets.values()) == ['new']
    with app.state.database.connect() as connection:
        assert text_models.key_for(app.state.vault, text_models.config_for(connection, 'recall')) == 'new'
