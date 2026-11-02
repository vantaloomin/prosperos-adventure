import asyncio
import os
import zlib
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from dungeon import story
from dungeon.authors_note import NOTE_CLOSE
from dungeon.clock import FixedClock
from dungeon.identity import CLIENT_HEADER
from dungeon.main import create_app
from dungeon.providers.chat import Chunk
from dungeon.providers.vault import MemoryVault
from dungeon.world import catalog

START = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)

# The app ships one city. The tests load these copies instead, as built-in cities, with the featured list from before, so every era and kind of city
# they cover stays covered. They live only here: not in the package data.
SHIPPED_CITIES, SHIPPED_FEATURED = catalog.BUILTIN_CITIES, catalog.FEATURED
catalog.BUILTIN_CITIES = Path(__file__).parent / 'fixtures' / 'cities'
catalog.FEATURED = Path(__file__).parent / 'fixtures' / 'featured.json'
catalog.reload()
catalog._featured.cache_clear()
# The tests were written with Baltimore as the city a workspace falls back to; the app's own is the shipped city.
SHIPPED_DEFAULT_CITY, story.DEFAULT_CITY = story.DEFAULT_CITY, 'baltimore'


class FakeProvider:
    """Records each request and replies with scripted chunks."""

    def __init__(self):
        self.requests = []
        self.replies = []
        self.before_finish = None
        self.error = None
        self.respond = None
        self.delay = 0

    async def stream(self, config, key, system, messages):
        # `prompt` is what the reply is told besides the conversation: the system prompt and this reply's notes.
        latest = messages[-1]['content'] if messages and isinstance(messages[-1]['content'], str) else ''
        notes = latest.split(NOTE_CLOSE)[0] if NOTE_CLOSE in latest else ''
        self.requests.append({'config': config, 'key': key, 'system': system, 'messages': messages,
                              'prompt': f'{system}\n\n{notes}'})
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error:
            raise self.error
        if self.respond:
            chunks = self.respond(system, messages)
        else:
            chunks = self.replies.pop(0) if self.replies else [Chunk('Hello again.'), Chunk('', 'stop')]
        for chunk in chunks:
            yield chunk
        if self.before_finish:
            self.before_finish()


@pytest.fixture(autouse=True)
def no_pc_timezone(monkeypatch):
    """Tests run in UTC whatever the machine's zone is; test_local_zone sets one where it needs it."""
    monkeypatch.setattr('dungeon.local_zone.detect', lambda: None)


@pytest.fixture(autouse=True)
def no_graphics_card(monkeypatch):
    """Tests never ask the test machine for its graphics cards (nvidia-smi, PowerShell); tests/test_hardware.py and
    tests/test_image_fit.py hand in the cards they need."""
    monkeypatch.setattr('dungeon.hardware.find_gpus', lambda memory: ([], 'No graphics card in tests.'))


@pytest.fixture(autouse=True)
def no_hold_after_replies(monkeypatch):
    """Background work would wait for the user to pause after each reply; tests/test_scheduling.py checks that."""
    monkeypatch.setattr('dungeon.providers.scheduling.HOLD_AFTER_REPLY', 0)


@pytest.fixture(autouse=True)
def no_life_cards(monkeypatch):
    """Life Cards drawn into the story (dungeon/happenings.py) factions' clocks moving (dungeon/factions.py) and
    the director's note (dungeon/director.py) would add events to unrelated tests' turns; tests/test_happenings.py and tests/test_factions.py turn them on."""
    monkeypatch.setattr('dungeon.happenings.ACTIVE', False)
    monkeypatch.setattr('dungeon.factions.ACTIVE', False)
    monkeypatch.setattr('dungeon.director.ACTIVE', False)


@pytest.fixture(autouse=True)
def no_turnover(monkeypatch):
    """Townsfolk moving away and newcomers (dungeon/world/turnover.py) would change who unrelated tests meet as
    their clocks move on; tests/test_turnover.py turns it on. Each test also starts from the usual town levels."""
    from dungeon.clock import Clock
    from dungeon.world import turnover
    monkeypatch.setattr(turnover, 'ACTIVE', False)
    monkeypatch.setattr(turnover, 'STATE', turnover.Levels(Clock()))


def pytest_collection_modifyitems(config, items):
    """DUNGEON_TEST_SHARD=2/3 runs the second third of the tests, picked by test name, so a slow CI runner can
    spread one suite over several jobs (.github/workflows/ci.yml)."""
    shard = os.environ.get('DUNGEON_TEST_SHARD')
    if not shard:
        return
    index, count = (int(part) for part in shard.split('/'))
    kept, dropped = [], []
    for item in items:
        (kept if zlib.crc32(item.nodeid.encode()) % count == index - 1 else dropped).append(item)
    config.hook.pytest_deselected(items=dropped)
    items[:] = kept


@pytest.fixture
def clock():
    return FixedClock(START)


@pytest.fixture
def provider():
    return FakeProvider()


@pytest.fixture
def app(tmp_path, clock, provider):
    return create_app(tmp_path / 'workspace' / 'dungeon.sqlite3', clock=clock, vault=MemoryVault(),
                      provider=provider, background=False)


@pytest.fixture
def client(app):
    with TestClient(app, headers={CLIENT_HEADER: 'workspace'}) as test_client:
        yield test_client


@pytest.fixture
def connected(client):
    response = client.put('/api/connection', json={'base_url': 'http://127.0.0.1:1234/v1', 'model': 'local-model',
                                                   'api_key': 'secret-key'})
    assert response.status_code == 200, response.text
    return response.json()


def tell(client, text, client_id):
    """One turn of the story (dungeon/story.py): the user's words and the narrator's reply."""
    response = client.post('/api/story/messages', json={'text': text, 'client_id': client_id})
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture
def told(client, connected):
    """A world with a story under way: one turn told."""
    return tell(client, 'I step inside out of the rain.', 'told-0001')


def ok(response):
    assert response.status_code == 200, response.text
    return response.json()


def narrator(provider) -> dict:
    """The last request to the narrator, past the Continuity model's questions after the turn."""
    from dungeon import chapters, record
    return [request for request in provider.requests if request['system'] != chapters.SUMMARIZE
            and not request['system'].startswith(record.EXTRACT)][-1]
