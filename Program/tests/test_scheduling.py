"""Background work waits for the user to pause on a model server that keeps only the last prompt it read."""
import asyncio

from dungeon.providers import scheduling
from dungeon.providers.scheduling import CONVERSATION, MAINTENANCE, RequestScheduler

LOCAL = {'base_url': 'http://127.0.0.1:1234/v1'}
ONLINE = {'base_url': 'https://openrouter.ai/api/v1'}


async def background_runs(scheduler, config, wait=0.2):
    async with scheduler.reserve(config, CONVERSATION):
        pass
    try:
        async with asyncio.timeout(wait):
            async with scheduler.reserve(config, MAINTENANCE):
                return True
    except TimeoutError:
        return False


def test_background_work_waits_after_a_reply_on_a_local_model(monkeypatch):
    monkeypatch.setattr(scheduling, 'HOLD_AFTER_REPLY', 0.5)
    assert asyncio.run(background_runs(RequestScheduler(), LOCAL)) is False
    assert asyncio.run(background_runs(RequestScheduler(), LOCAL, wait=2)) is True, 'it runs once the user pauses'


def test_an_online_provider_keeps_many_prompts_so_nothing_waits(monkeypatch):
    monkeypatch.setattr(scheduling, 'HOLD_AFTER_REPLY', 60)
    assert asyncio.run(background_runs(RequestScheduler(), ONLINE)) is True
