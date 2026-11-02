"""Bonds, earned by warm feelings or sworn, and the Life Cards that name them (dungeon/bonds.py)."""
from datetime import date

from conftest import Chunk, tell
from test_happenings import dealt  # noqa: F401
from test_lies import begin

from dungeon import bonds, feelings, growth, happenings, story_people
from dungeon.life import cards

NOW = '2026-10-01T12:00:00Z'
HESK = {'sheet': {'key': 'hesk', 'full': 'Hesk Aldane', 'name': 'Hesk', 'role': 'woodcutter'}}


def met(connection, key='hesk', name='Hesk Aldane'):
    connection.execute('INSERT INTO story_people (key, city_id, name, first_met_at, last_met_at, last_day) VALUES '
                       "(?, 'kingswood', ?, ?, ?, '2026-10-01')", (key, name, NOW, NOW))


def test_warm_feelings_earn_a_bond_and_a_fate_breaks_it(app, client):
    begin(client)
    with app.state.database.connect(write=True) as connection:
        met(connection)
        feelings.change(connection, 'hesk', {'trust': 2, 'affection': 2})
        feelings.change(connection, 'hesk', {'trust': 1})
        assert bonds.bonds(connection) == []
        feelings.change(connection, 'hesk', {'affection': 1})
        assert [(row['name'], row['how'], row['state']) for row in bonds.bonds(connection)] == [
            ('Hesk Aldane', 'earned', 'whole')]
        assert story_people.known(connection)['hesk']['bond'] == 'earned'
        assert 'They are bonded to the character' in story_people.remembered(story_people.known(connection)['hesk'])
        assert growth.view(connection, True)['bonds'] == {
            'word': 'one true bond', 'count': 1,
            'bonds': [{'key': 'hesk', 'name': 'Hesk Aldane', 'how': 'earned', 'state': 'whole'}]}
        assert 'count' not in growth.view(connection, False)['bonds']
        connection.execute("INSERT INTO story_fates (key, name, state, since) VALUES ('hesk', 'Hesk Aldane', "
                           "'turned', ?)", (NOW,))
        assert bonds.bonds(connection)[0]['state'] == 'broken' and bonds.whole(connection) == []
        assert story_people.known(connection)['hesk']['bond'] is None
        assert bonds.track(connection, True)['word'] == 'no one to call on'


def test_a_pledge_to_someone_there_swears_a_bond_once(app, client):
    begin(client)
    with app.state.database.connect(write=True) as connection:
        assert bonds.sworn(connection, 'I stand by Hesk.', [HESK], NOW) == []
        assert bonds.sworn(connection, 'I swear to protect them all.', [HESK], NOW) == []
        lines = bonds.sworn(connection, 'I swear to stand by you, Hesk, whatever comes.', [HESK], NOW)
        assert lines == ["The player's character binds themselves to Hesk Aldane: a bond from now on, kept by the game."]
        assert bonds.sworn(connection, 'I vow to protect Hesk.', [HESK], NOW) == []
        assert bonds.bonds(connection)[0]['how'] == 'sworn'
    assert bonds.word(0) == 'no one to call on' and bonds.word(3) == 'a few who would stand by them' and \
        bonds.word(9) == 'well bonded, with friends in many places'


def test_bond_cards_come_into_play_with_a_bond(app, client, dealt):  # noqa: F811
    begin(client)
    level = {'levels': cards.PRESETS['unflinching'], 'veils': []}
    data = {'intensity': {'drama': 'merciless'}}
    with app.state.database.connect(write=True) as connection:
        dealt.next = 'bond-dice-debt'
        happenings.draw(connection, 'town', 's', 'kingswood', 'felled-oak', data, level, date(1290, 5, 1))
        assert 'bond-dice-debt' in dealt.calls[-1]['recent']
        met(connection)
        bonds.forge(connection, 'hesk', 'Hesk Aldane', 'sworn', NOW)
        drawn = happenings.draw(connection, 'town', 's', 'kingswood', 'felled-oak', data, level, date(1290, 5, 1))
        assert 'bond-dice-debt' not in dealt.calls[-1]['recent'] and drawn['bond']['key'] == 'hesk'
        lines, _ = happenings.play(connection, drawn, {
            'people': [], 'name': 'Agna', 'data': {'name': 'Kingswood'}, 'logged': NOW, 'now': date(1290, 5, 1),
            'city': 'kingswood', 'rng': None, 'levels': None, 'day': '1290-05-01'})
        assert lines[0].startswith('Hesk Aldane has been jumpy for days')
        assert any(line.startswith('Hesk Aldane wants something of the character') for line in lines)
        before = feelings.of(story_people.known(connection)['hesk'])['trust']
        happenings.feeling(connection, {'who': 'bond', 'axis': 'trust', 'shift': -1}, {'npc': None, 'bond': drawn['bond'],
                                                                                       'title': 'a test'})
        assert feelings.of(story_people.known(connection)['hesk'])['trust'] == before - 1


def test_the_narrator_hears_a_sworn_bond(client, connected, provider, monkeypatch):
    begin(client)
    sworn = []

    def swearing(connection, text, people, now):
        sworn.append(text)
        return ["The player's character binds themselves to Corin Ashby: a bond from now on, kept by the game."]

    monkeypatch.setattr(bonds, 'sworn', swearing)
    provider.replies = [[Chunk('He nods.'), Chunk('', 'stop')]]
    tell(client, 'I swear to stand by you, Corin.', 'story-0001')
    assert sworn == ['I swear to stand by you, Corin.']
    assert '## A bond (decided by the game)\n- The player' in provider.requests[-1]['system']
