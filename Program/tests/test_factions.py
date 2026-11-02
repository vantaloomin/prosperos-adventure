"""Factions (dungeon/factions.py): clocks on the world clock, the news reaching town, standing, the narrator's view."""
from datetime import datetime, timedelta

import pytest
from conftest import tell
from test_happenings import dealt  # noqa: F401 - a fixture
from test_inventory import begin
from test_travel import ok, reply

from dungeon import factions

DAY = datetime(1290, 5, 1, 12)


class Always:
    def randint(self, low, high):
        return low


@pytest.fixture
def running(monkeypatch):
    monkeypatch.setattr(factions, 'ACTIVE', True)


def test_clocks_run_by_the_day_and_fill_into_the_record(app, running):
    with app.state.database.connect(write=True) as connection:
        factions.advance(connection, 'vallarith', DAY, DAY + timedelta(hours=20), '2026-10-22', Always())
        assert factions.filled(connection, 'kingdom-of-cyrel', 'war-levy') == 1
        factions.advance(connection, 'vallarith', DAY, DAY + timedelta(days=5), '2026-10-22', Always())
        # Four segments: the levy is done, and it stops there.
        assert factions.filled(connection, 'kingdom-of-cyrel', 'war-levy') == 4
        assert factions.filled(connection, 'kingdom-of-cyrel', 'retake-adlmyr') == 6
        truth = connection.execute("SELECT truth, text FROM record_entries WHERE subject='The Kingdom of Cyrel'"
                                   ).fetchall()
        assert [(row['truth'], row['text'][:16]) for row in truth] == [('world', "Cyrel's war levy")]
        # Its news reaches the character once.
        assert factions.news(connection, 'vallarith', '2026-10-22')[0].startswith("News reaches town: Cyrel's war levy")
        assert factions.news(connection, 'vallarith', '2026-10-22') == []


def test_standing_moves_within_its_range_and_reads_as_words(app):
    with app.state.database.connect(write=True) as connection:
        guild = factions.find('vallarith', 'cyrel-timber-guild')
        assert factions.shift(connection, guild, 3) == f"The character's standing with {guild['name']}: now trusted."
        factions.shift(connection, guild, 9)
        assert factions.standing(connection, 'cyrel-timber-guild') == factions.HIGHEST
        factions.shift(connection, guild, -20)
        assert factions.standing_word(factions.standing(connection, 'cyrel-timber-guild')) == 'an enemy'


def test_the_town_hears_the_news_and_the_narrator_knows_the_powers(client, connected, provider, app, running):
    begin(client)
    with app.state.database.connect(write=True) as connection:
        factions.tick(connection, 'vallarith', factions.find('vallarith', 'brynwyr-high-elves'),
                      factions.find('vallarith', 'brynwyr-high-elves')['clocks'][0], 6, DAY, '2026-10-22')
    reply(provider, 'The village talks of nothing else.')
    tell(client, 'I listen to the talk.', 'story-0001')
    narrator = provider.requests[-1]['system']
    assert 'News reaches town: The wardens of Brynwyr move the border stones' in narrator
    assert '## The powers here' in narrator and 'Move the border stones 6 of 6' in narrator
    assert 'War levy 0 of 4' in narrator
    known = {item['id']: item for item in ok(client.get('/api/story'))['factions']}
    assert {'kingdom-of-cyrel', 'cyrel-timber-guild', 'brynwyr-high-elves'} <= set(known)
    assert known['kingdom-of-cyrel']['standing'] == 'unknown' and 'kingdom-of-asania' not in known
    # Told once.
    reply(provider, 'Quiet.')
    tell(client, 'I finish my drink.', 'story-0002')
    assert 'News reaches town' not in provider.requests[-1]['system']


def test_a_card_moves_a_local_factions_clock(client, connected, provider, app, dealt):  # noqa: F811
    begin(client)
    dealt.next = 'soft-lender'
    reply(provider, 'A smiling man with a ledger.')
    tell(client, 'I walk the green.', 'story-0001')
    with app.state.database.connect() as connection:
        moved = sum(row['filled'] for row in connection.execute('SELECT filled FROM story_clocks').fetchall())
    assert moved == 1
