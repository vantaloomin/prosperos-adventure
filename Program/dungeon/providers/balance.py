"""Credits and usage for services that report them for free: no model is called and no tokens are spent.

OpenRouter (/credits and /key), NanoGPT (/check-balance), DeepSeek (/user/balance), Moonshot
(/users/me/balance) and a Codex ChatGPT login (app-server account/rateLimits/read). Anything else, or any
failure, gives None, so the Models section simply shows nothing for that profile.
"""
import asyncio
import logging
import time
from datetime import UTC, datetime
from urllib.parse import urlsplit

import httpx

from dungeon.providers.urls import network

log = logging.getLogger(__name__)
SECONDS = 10
# A lookup is kept this long, so opening Settings again does not ask the service again.
KEPT_FOR = 300
_kept: dict[tuple, tuple[float, dict | None]] = {}


def money(label: str, amount, currency: str = 'USD', of=None) -> dict | None:
    try:
        item = {'label': label, 'amount': round(float(amount), 2), 'currency': currency}
        if of is not None:
            item['of'] = round(float(of), 2)
        return item
    except (TypeError, ValueError):
        return None


def service_for(config: dict) -> str | None:
    """Which balance lookup a profile's address supports, by provider or by the host it calls."""
    provider = config.get('provider')
    if provider == 'codex':
        return 'codex'
    if provider in {'local', 'kobold'}:
        return None
    host = (urlsplit(config.get('base_url') or '').hostname or '').lower()
    if host == 'openrouter.ai':
        return 'openrouter'
    if host in {'nano-gpt.com', 'api.nano-gpt.com'}:
        return 'nanogpt'
    if host == 'api.deepseek.com':
        return 'deepseek'
    if host in {'api.moonshot.ai', 'api.moonshot.cn'}:
        return 'moonshot'
    return None


def has_lookup(config: dict) -> bool:
    return service_for(config) is not None


async def get_json(client, url, key, **options):
    method = options.pop('method', 'GET')
    headers = options.pop('headers', None) or {'Authorization': f'Bearer {key}'}
    response = await client.request(method, url, headers=headers)
    response.raise_for_status()
    return response.json()


async def openrouter(client, config, key) -> list[dict]:
    base = config['base_url'].rstrip('/')
    account, this_key = await asyncio.gather(get_json(client, f'{base}/credits', key),
                                             get_json(client, f'{base}/key', key), return_exceptions=True)
    items = []
    if isinstance(account, dict) and isinstance(data := account.get('data'), dict):
        total, used = data.get('total_credits'), data.get('total_usage')
        if isinstance(total, int | float) and isinstance(used, int | float):
            items.append(money('Credits left', total - used, of=total))
    if isinstance(this_key, dict) and isinstance(data := this_key.get('data'), dict):
        if isinstance(data.get('limit'), int | float) and isinstance(data.get('limit_remaining'), int | float):
            items.append(money('Key limit left', data['limit_remaining'], of=data['limit']))
        if isinstance(data.get('usage_daily'), int | float):
            items.append({**money('Used today', data['usage_daily']), 'spent': True})
        free = data.get('free_model_daily_requests')
        if data.get('is_free_tier') and isinstance(free, dict) and isinstance(free.get('limit'), int) and free['limit']:
            items.append({'label': 'Free requests today', 'percent_used': percent(free.get('used'), free['limit'])})
    return items


async def nanogpt(client, config, key) -> list[dict]:
    host = urlsplit(config['base_url']).hostname
    data = await get_json(client, f'https://{host}/api/check-balance', key, method='POST',
                          headers={'x-api-key': key or ''})
    return [money('Balance', data.get('usd_balance'))]


async def deepseek(client, config, key) -> list[dict]:
    data = await get_json(client, 'https://api.deepseek.com/user/balance', key)
    return [money('Balance', info.get('total_balance'), str(info.get('currency') or 'USD'))
            for info in data.get('balance_infos') or [] if isinstance(info, dict)]


async def moonshot(client, config, key) -> list[dict]:
    host = urlsplit(config['base_url']).hostname
    data = await get_json(client, f'https://{host}/v1/users/me/balance', key)
    currency = 'CNY' if host.endswith('.cn') else 'USD'
    return [money('Balance', (data.get('data') or {}).get('available_balance'), currency)]


def percent(used, limit) -> int | None:
    if isinstance(used, int | float) and isinstance(limit, int | float) and limit > 0:
        return max(0, min(100, round(used * 100 / limit)))
    return None


def window_name(minutes) -> str:
    if not isinstance(minutes, int) or minutes <= 0:
        return 'Usage limit'
    if minutes == 10080:
        return 'Weekly limit'
    if minutes % 1440 == 0:
        return f'{minutes // 1440}-day limit'
    if minutes % 60 == 0:
        return f'{minutes // 60}-hour limit'
    return f'{minutes}-minute limit'


def codex_items(limits: dict) -> list[dict]:
    items = []
    for window in (limits.get('primary'), limits.get('secondary')):
        if isinstance(window, dict) and isinstance(window.get('usedPercent'), int | float):
            item = {'label': window_name(window.get('windowDurationMins')),
                    'percent_used': max(0, min(100, round(window['usedPercent'])))}
            if isinstance(window.get('resetsAt'), int | float):
                item['resets_at'] = datetime.fromtimestamp(window['resetsAt'], UTC).isoformat()
            items.append(item)
    credits = limits.get('credits')
    if isinstance(credits, dict) and credits.get('hasCredits') and not credits.get('unlimited'):
        try:
            items.append({'label': 'Credits', 'count': round(float(credits.get('balance')), 2)})
        except (TypeError, ValueError):
            pass
    return items


LOOKUPS = {'openrouter': openrouter, 'nanogpt': nanogpt, 'deepseek': deepseek, 'moonshot': moonshot}


async def lookup(config: dict, key: str | None, transport=None, codex=None) -> dict | None:
    service = service_for(config)
    if service is None:
        return None
    try:
        async with asyncio.timeout(25 if service == 'codex' else SECONDS):
            if service == 'codex':
                limits = await codex.usage()
                items, plan = codex_items(limits), limits.get('planType')
            else:
                if not key:
                    return None
                async with httpx.AsyncClient(transport=transport, timeout=SECONDS, follow_redirects=False,
                                             **network(config.get('base_url') or '')) as client:
                    items, plan = await LOOKUPS[service](client, config, key), None
    except Exception as error:  # noqa: BLE001 - a lookup that fails shows nothing, never an error
        log.info('No balance from %s: %s', service, type(error).__name__)
        return None
    items = [item for item in items if item and item.get('percent_used', 0) is not None]
    if not items:
        return None
    return {'items': items, 'plan': plan.title() if isinstance(plan, str) and plan else None,
            'checked_at': datetime.now(UTC).isoformat()}


async def cached(profile_key: tuple, config: dict, key: str | None, fresh: bool = False, **options) -> dict | None:
    """A recent lookup for the same profile version, unless `fresh` asks the service again."""
    now = time.monotonic()
    kept = _kept.get(profile_key)
    if kept and not fresh and now - kept[0] < KEPT_FOR:
        return kept[1]
    result = await lookup(config, key, **options)
    _kept[profile_key] = (now, result)
    return result
