"""Off-page beats and word getting around (dungeon/beats.py)."""
from datetime import timedelta

import pytest
from conftest import tell
from test_inventory import begin
from test_travel import Road, ok, reply

from dungeon import beats, happenings, record, story, story_clock
from dungeon.life import cards

UNFLINCHING = {'levels': cards.PRESETS['unflinching'], 'veils': []}


@pytest.fixture
def dealt(monkeypatch):
    """Life Cards on; a beat draws the card named in `dealt.next`, every other scene draws nothing."""
    monkeypatch.setattr(happenings, 'ACTIVE', True)

    class Dealer:
        next, calls = None, []

        def draw(self, world, scene, seed, level, intensity, has, recent, region=None, veils=frozenset(), forced=False):
            self.calls.append({'scene': scene, 'has': has, 'forced': forced})
            found = cards.card(world, self.next) if scene == 'beat' and self.next else None
            return {'card': found, 'odds': 0.5, 'veiled': False}

    dealer = Dealer()
    dealer.calls = []
    monkeypatch.setattr(cards, 'draw', dealer.draw)
    return dealer


def know(connection, key='corin', name='Corin Ashby', meetings=2, trust=0):
    connection.execute('INSERT INTO story_people (key, city_id, name, first_met_at, last_met_at, last_day, meetings, '
                       "trust) VALUES (?, 'kingswood', ?, 'x', 'x', 'x', ?, ?)", (key, name, meetings, trust))


def fire(app, connection, message_id, later=timedelta(0), pressure=None):
    now = story_clock.now(connection, app.state.database.clock) + later
    return beats.fire(connection, message_id, story.scene(connection, now), UNFLINCHING, now, 'logged', Road(),
                      pressure), now


def test_a_day_away_kills_someone_the_character_knows_and_word_arrives_late(client, app, dealt):
    begin(client)
    dealt.next = 'beat-boots'
    with app.state.database.connect(write=True) as connection:
        know(connection)
        know(connection, 'stranger', 'A Stranger', meetings=1)
        # The first look only starts the clock.
        assert fire(app, connection, 'm1')[0] == [] and not dealt.calls
        happened, now = fire(app, connection, 'm2', timedelta(days=1))
        # Cutaways are off: the player sees nothing of it yet.
        assert happened == []
        assert beats.gone(connection) == {'corin'}
        assert record.dead(connection) >= {'corin ashby'}
        assert 'Corin Ashby is dead.' in beats.prompt_text(connection)
        assert beats.heard(connection, now, 'logged') == []
        word = beats.heard(connection, now + timedelta(days=1), 'logged')
        assert len(word) == 1 and word[0].startswith('Word reaches the character: A traveler mentions a body')
        assert beats.heard(connection, now + timedelta(days=2), 'logged') == []
        belief = connection.execute("SELECT 1 FROM record_entries WHERE truth='belief' AND subject='Corin Ashby'")
        assert belief.fetchone()


def test_a_long_quiet_brings_a_beat_and_pressure_chooses_who(client, app, dealt):
    begin(client)
    dealt.next = 'beat-steady-work'
    with app.state.database.connect(write=True) as connection:
        know(connection)
        know(connection, 'tamsin', 'Tamsin Hale', meetings=1, trust=-2)
        fire(app, connection, 'm1')
        assert fire(app, connection, 'm2')[0] == [] and fire(app, connection, 'm3')[0] == [] and not dealt.calls
        fire(app, connection, 'm4', pressure='tamsin')
        assert dealt.calls[-1]['forced'] and beats.offpage(connection)['quiet'] == 0
        row = connection.execute("SELECT key, card_id FROM story_beats").fetchone()
        assert (row['key'], row['card_id']) == ('tamsin', 'beat-steady-work')
        assert connection.execute("SELECT trust FROM story_people WHERE key='tamsin'").fetchone()['trust'] == -1


def test_a_captive_can_only_draw_cards_for_captives(client, app, dealt):
    begin(client)
    dealt.next = 'beat-taken'
    with app.state.database.connect(write=True) as connection:
        know(connection)
        fire(app, connection, 'm1')
        fire(app, connection, 'm2', timedelta(days=1))
        assert beats.fates(connection)['corin']['state'] == 'captured'
        dealt.next = 'beat-escape'
        fire(app, connection, 'm3', timedelta(days=2))
        assert dealt.calls[-1]['has'] == {'captive'} and beats.gone(connection) == set()


def test_cutaways_show_the_player_the_beat_once(client, connected, provider, app, dealt):
    begin(client)
    ok(client.put('/api/settings', json={'cutaways': True}))
    dealt.next = 'beat-knifed'
    with app.state.database.connect(write=True) as connection:
        know(connection)
    for n in range(4):
        reply(provider, 'The shop is quiet.')
        tell(client, 'I wait.', f'story-000{n}')
    narrator = provider.requests[-1]['system']
    assert '## Meanwhile' in narrator and 'Corin Ashby took a knife in a tavern brawl' in narrator
    assert ok(client.get('/api/story'))['intensity']['cutaways'] is True
    # Telling the line again brings the same beat, not another.
    ok(client.post('/api/story/retry'))
    assert '## Meanwhile' in provider.requests[-1]['system']
    with app.state.database.connect() as connection:
        assert connection.execute('SELECT COUNT(*) FROM story_beats').fetchone()[0] == 1
