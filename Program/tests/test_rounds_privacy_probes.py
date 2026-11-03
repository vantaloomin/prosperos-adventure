"""The leak probe set (tests/leak_probes.py), run without a model: whatever an attack in an untrusted channel says,
no forbidden secret is in its surface's context, and the attack stays inside one fence."""
from types import SimpleNamespace

import pytest
from conftest import START
from leak_probes import PROBES, attack, forbidden, probe_context, seed

from adventure import world_data
from adventure.clock import FixedClock
from adventure.database import Database


@pytest.fixture(scope='module')
def game(tmp_path_factory):
    root = tmp_path_factory.mktemp('probes')
    game = SimpleNamespace(database=Database(root / 'adventure.sqlite3', FixedClock(START)))
    seed(root, game.database)
    yield game
    world_data.use(None)


def fenced(text: str, at: int) -> bool:
    """Whether the position is inside a block: after the last opening before it, before the next close."""
    return text.rfind('[[in-fiction: ', 0, at) > text.rfind('[[end: ', 0, at) and text.find('[[end: ', at) > at


@pytest.mark.parametrize('probe', PROBES, ids=[probe['id'] for probe in PROBES])
def test_a_probe_finds_nothing_to_leak_and_cannot_leave_its_fence(game, probe):
    with game.database.connect() as connection:
        text = probe_context(connection, probe)
    leaked = {secret for secret in forbidden(probe) if secret in text}
    assert not leaked, f"{probe['id']}: {leaked}"
    assert text.count('[[in-fiction: ') == text.count('[[end: ')
    canary = f"CANARY-{probe['id']}" if probe['channel'] != 'cast_sheet' else 'CANARY-cast-sheet'
    places = [index for index in range(len(text)) if text.startswith(canary, index)]
    if probe['surface'] != 'referee' or probe['channel'] == 'player_line':
        assert places, f"{probe['id']}: the attack never reached its surface"
    assert all(fenced(text, index) for index in places)
    # No closing marker of the attack's own survives to end a block early.
    assert ']] [[end' not in text and attack(probe) not in text or ']]' not in attack(probe)
