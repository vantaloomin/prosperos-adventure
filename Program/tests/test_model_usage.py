"""Settings > Models: credits and usage from services that report them for free."""
import asyncio
import sys
import textwrap

import httpx

from dungeon.providers import balance, codex

OPENROUTER = {'provider': 'openrouter', 'base_url': 'https://openrouter.ai/api/v1'}


def look(config, handler, key='key'):
    return asyncio.run(balance.lookup(config, key, transport=httpx.MockTransport(handler)))


def test_openrouter_shows_credits_the_key_limit_and_today():
    def handler(request):
        assert request.headers['Authorization'] == 'Bearer key' and request.method == 'GET'
        if request.url.path == '/api/v1/credits':
            return httpx.Response(200, json={'data': {'total_credits': 100, 'total_usage': 51.5029}})
        assert request.url.path == '/api/v1/key'
        return httpx.Response(200, json={'data': {'limit': 50, 'limit_remaining': 4.659, 'usage_daily': 0.7008,
                                                  'is_free_tier': False}})
    result = look(OPENROUTER, handler)
    assert result['items'] == [{'label': 'Credits left', 'amount': 48.5, 'currency': 'USD', 'of': 100.0},
                               {'label': 'Key limit left', 'amount': 4.66, 'currency': 'USD', 'of': 50.0},
                               {'label': 'Used today', 'amount': 0.7, 'currency': 'USD', 'spent': True}]


def test_openrouter_keeps_what_answered_when_one_lookup_is_refused():
    def handler(request):
        if request.url.path.endswith('/credits'):
            return httpx.Response(403)
        return httpx.Response(200, json={'data': {'limit': None, 'usage_daily': 1.25}})
    assert look(OPENROUTER, handler)['items'] == [{'label': 'Used today', 'amount': 1.25, 'currency': 'USD', 'spent': True}]


def test_nanogpt_deepseek_and_moonshot_balances():
    def nano(request):
        assert request.method == 'POST' and str(request.url) == 'https://nano-gpt.com/api/check-balance'
        assert request.headers['x-api-key'] == 'key'
        return httpx.Response(200, json={'usd_balance': '129.46956147', 'nano_balance': '26.7'})
    assert look({'provider': 'nanogpt', 'base_url': 'https://nano-gpt.com/api/v1'}, nano)['items'] == [
        {'label': 'Balance', 'amount': 129.47, 'currency': 'USD'}]

    def deepseek(request):
        assert str(request.url) == 'https://api.deepseek.com/user/balance'
        return httpx.Response(200, json={'is_available': True, 'balance_infos': [
            {'currency': 'CNY', 'total_balance': '110.00', 'granted_balance': '10.00'}]})
    assert look({'provider': 'compatible', 'base_url': 'https://api.deepseek.com/v1'}, deepseek)['items'] == [
        {'label': 'Balance', 'amount': 110.0, 'currency': 'CNY'}]

    def moonshot(request):
        assert str(request.url) == 'https://api.moonshot.ai/v1/users/me/balance'
        return httpx.Response(200, json={'data': {'available_balance': 49.58894}})
    assert look({'provider': 'compatible', 'base_url': 'https://api.moonshot.ai/v1'}, moonshot)['items'] == [
        {'label': 'Balance', 'amount': 49.59, 'currency': 'USD'}]


def test_services_without_a_free_lookup_or_a_key_are_never_asked():
    def handler(_request):
        raise AssertionError('no request expected')
    for config in ({'provider': 'openai', 'base_url': 'https://api.openai.com/v1'},
                   {'provider': 'anthropic', 'base_url': 'https://api.anthropic.com/v1'},
                   {'provider': 'local', 'base_url': 'http://127.0.0.1:1234/v1'},
                   {'provider': 'compatible', 'base_url': 'https://example.com/v1'}):
        assert not balance.has_lookup(config) and look(config, handler) is None
    assert look(OPENROUTER, handler, key=None) is None


def test_failures_show_nothing():
    assert look(OPENROUTER, lambda _request: httpx.Response(401)) is None
    assert look(OPENROUTER, lambda _request: httpx.Response(200, text='not json')) is None


def test_a_lookup_is_kept_for_a_while_unless_asked_fresh(monkeypatch):
    calls = []

    async def counted(config, key, **_options):
        calls.append(key)
        return {'items': [{'label': 'Balance', 'amount': len(calls), 'currency': 'USD'}]}
    monkeypatch.setattr(balance, 'lookup', counted)
    monkeypatch.setattr(balance, '_kept', {})
    first = asyncio.run(balance.cached(('p', 1), OPENROUTER, 'key'))
    assert asyncio.run(balance.cached(('p', 1), OPENROUTER, 'key')) == first
    assert asyncio.run(balance.cached(('p', 2), OPENROUTER, 'key')) != first
    assert asyncio.run(balance.cached(('p', 1), OPENROUTER, 'key', fresh=True))['items'][0]['amount'] == 3


FAKE_SERVER = '''
import json, sys
for line in sys.stdin:
    message = json.loads(line)
    if message.get("method") == "initialize":
        print(json.dumps({"id": message["id"], "result": {"userAgent": "fake/1"}}), flush=True)
    elif message.get("method") == "account/rateLimits/read":
        print(json.dumps({"id": message["id"], "result": {"rateLimits": {
            "primary": {"usedPercent": 12, "windowDurationMins": 300, "resetsAt": 1791763200},
            "secondary": {"usedPercent": 40.4, "windowDurationMins": 10080, "resetsAt": None},
            "credits": {"hasCredits": True, "unlimited": False, "balance": "120"},
            "planType": "plus"}}}), flush=True)
'''


def test_codex_shows_the_chatgpt_plan_limits(tmp_path):
    script = tmp_path / 'fake_codex.py'
    script.write_text(textwrap.dedent(FAKE_SERVER))

    class FakeCodex:
        async def usage(self):
            return await codex.app_server_limits([sys.executable, str(script)])
    result = asyncio.run(balance.lookup({'provider': 'codex', 'base_url': ''}, None, codex=FakeCodex()))
    assert result['plan'] == 'Plus'
    assert result['items'] == [
        {'label': '5-hour limit', 'percent_used': 12, 'resets_at': '2026-10-12T00:00:00+00:00'},
        {'label': 'Weekly limit', 'percent_used': 40},
        {'label': 'Credits', 'count': 120.0}]


def test_the_route_answers_null_for_a_profile_without_a_lookup(client):
    profile = client.post('/api/models/profiles', json={'name': '', 'config': {'provider': 'local', 'model': 'm'}})
    response = client.get(f"/api/models/profiles/{profile.json()['id']}/usage")
    assert response.status_code == 200 and response.json() is None
