"""The party: people the character asks along decide for themselves, travel with them, and leave (adventure/party.py)."""
from conftest import Chunk, tell
from test_bonds import met
from test_lies import Dice, begin

from adventure import bonds, feelings, party, story, story_clock

NOW, DAY = '2026-10-01T12:00:00Z', '2026-10-01'
HESK = {'sheet': {'key': 'hesk', 'full': 'Hesk Aldane', 'name': 'Hesk', 'role': 'woodcutter', 'occupation': ''}}
ILSE = {'sheet': {'key': 'ilse', 'full': 'Ilse Brand', 'name': 'Ilse', 'role': 'baker', 'occupation': 'baker'}}


def view(connection, people, known=None):
    return {'people': people, 'known': known if known is not None else story.story_people.known(connection),
            'city': {'id': 'kingswood'}, 'local_time': '2026-10-01T12:00'}


def test_asked_along_they_decide_for_themselves(app, client):
    begin(client)
    with app.state.database.connect(write=True) as connection:
        met(connection)
        # Someone in two minds: the character's Allure is rolled, hard.
        assert 'turns the character down' in party.turn(connection, 'm1', view(connection, [HESK]),
                                                        'Come with me, Hesk.', DAY, NOW, Dice(1))[0]
        assert party.members(connection) == []
        # Kept with the line.
        assert 'turns the character down' in party.turn(connection, 'm1', view(connection, [HESK]), 'whatever', DAY,
                                                        NOW, Dice(100))[0]
        feelings.change(connection, 'hesk', {'trust': -1})
        assert "won't come along" in party.turn(connection, 'm2', view(connection, [HESK]), 'Join us, Hesk?', DAY,
                                               NOW, Dice(100))[0]
        feelings.change(connection, 'hesk', {'trust': 2, 'affection': 2})
        lines = party.turn(connection, 'm3', view(connection, [HESK, ILSE]), 'Hesk, will you come along?', DAY, NOW,
                           Dice(1))
        assert lines == ['Hesk Aldane agrees to come along with the character, from now on, of their own will.']
        assert [row['name'] for row in party.members(connection)] == ['Hesk Aldane']
        # A bond is enough on its own; nobody else to ask means nothing happens.
        met(connection, 'ilse', 'Ilse Brand')
        bonds.forge(connection, 'ilse', 'Ilse Brand', 'sworn', NOW)
        assert party.turn(connection, 'm4', view(connection, [HESK, ILSE]), 'Come with me.', DAY, NOW, Dice(100)) == []
        assert 'agrees' in party.turn(connection, 'm5', view(connection, [HESK, ILSE]), 'Ilse, come with me.', DAY,
                                      NOW, Dice(100))[0]


def test_companions_leave_when_told_soured_or_gone(app, client):
    begin(client)
    with app.state.database.connect(write=True) as connection:
        for person in (HESK, ILSE):
            met(connection, person['sheet']['key'], person['sheet']['full'])
            bonds.forge(connection, person['sheet']['key'], person['sheet']['full'], 'sworn', NOW)
            party.turn(connection, f"join-{person['sheet']['key']}", view(connection, [person]), 'Come with me.',
                       DAY, NOW)
        assert party.keys(connection) == {'hesk', 'ilse'}
        assert party.turn(connection, 'm1', view(connection, []), 'You can go home now.', DAY, NOW) == []
        assert party.turn(connection, 'm2', view(connection, []), 'Ilse, you can go home.', DAY, NOW) == [
            'Ilse Brand leaves the character\'s company and goes back to their own life.']
        feelings.change(connection, 'hesk', {'trust': -2})
        feelings.change(connection, 'hesk', {'affection': -1})
        assert 'has had enough' in party.turn(connection, 'm3', view(connection, []), 'We walk on.', DAY, NOW)[0]
        assert party.members(connection) == []
        party.turn(connection, 'm4', view(connection, [ILSE]), 'Ilse, come with me.', DAY, NOW)
        connection.execute("INSERT INTO story_fates (key, name, state, since) VALUES ('ilse', 'Ilse Brand', 'dead', ?)",
                           (NOW,))
        assert party.members(connection) == []


def test_the_party_is_in_every_scene_with_the_character(app, client):
    begin(client)
    database = app.state.database
    with database.connect(write=True) as connection:
        here = story.scene(connection, story_clock.now(connection, database.clock))
        someone = here['people'][0]
        met(connection, someone['sheet']['key'], someone['sheet']['full'])
        bonds.forge(connection, someone['sheet']['key'], someone['sheet']['full'], 'sworn', NOW)
        party.turn(connection, 'm1', view(connection, [someone]), 'Come with me.', DAY, NOW)
    client.put('/api/story/scene', json={'city_id': 'kingswood', 'place_id': 'blackwood-smithy'})
    with database.connect() as connection:
        there = story.scene(connection, story_clock.now(connection, database.clock))
        found = [person for person in there['people'] if person['sheet']['key'] == someone['sheet']['key']]
        assert len(found) == 1 and found[0]['doing'] == party.DOING
        assert 'travel with the player\'s character as a companion' in story.scene_text(there)
        listed = next(person for person in story.people(connection, there) if person['key'] == someone['sheet']['key'])
        assert listed['party'] and listed['doing'] == 'travelling with you' and listed['place'] is None


def test_the_narrator_hears_who_joins(client, connected, provider, monkeypatch):
    begin(client)

    def joining(connection, message_id, view, text, day, now, rng=None, agents=frozenset(), choices=None):
        return ['Corin Ashby agrees to come along with the character, from now on, of their own will.']

    monkeypatch.setattr(party, 'turn', joining)
    provider.replies = [[Chunk('He shoulders his pack.'), Chunk('', 'stop')]]
    tell(client, 'Come with me, Corin.', 'story-0001')
    assert '## The party (decided by the game)\n- Corin Ashby agrees' in provider.requests[-1]['system']


def test_souring_never_sends_an_agent_away_but_feelings_still_limit_who_joins(app, client):
    # Agent chooses, feelings limit (docs/spec.md): an agent leaves by its own move, after a sign.
    begin(client)
    with app.state.database.connect(write=True) as connection:
        met(connection)
        feelings.change(connection, 'hesk', {'trust': -1})
        assert "won't come along" in party.turn(connection, 'm1', view(connection, [HESK]), 'Join us, Hesk?', DAY,
                                               NOW, Dice(100), agents={'hesk'})[0]
        bonds.forge(connection, 'hesk', 'Hesk Aldane', 'sworn', NOW)
        party.turn(connection, 'm2', view(connection, [HESK]), 'Come with me, Hesk.', DAY, NOW, agents={'hesk'})
        assert party.keys(connection) == {'hesk'}
        feelings.change(connection, 'hesk', {'trust': -2, 'affection': -2})
        assert party.turn(connection, 'm3', view(connection, []), 'We walk on.', DAY, NOW, agents={'hesk'}) == []
        assert party.keys(connection) == {'hesk'}
        # Told to go, they still part; on a Program mind, souring sends them away as before.
        assert party.turn(connection, 'm4', view(connection, []), 'We walk on.', DAY, NOW) != []
        assert party.keys(connection) == set()


def test_an_agent_asked_along_answers_for_themselves_within_what_feelings_allow(app, client):
    # Agent chooses, feelings limit (docs/spec.md): their answer replaces the bond, warmth and roll.
    begin(client)
    with app.state.database.connect(write=True) as connection:
        met(connection)
        # In two minds and the roll would fail: their yes stands.
        assert party.askable(connection, view(connection, [HESK]), 'Come with me, Hesk.')['sheet']['key'] == 'hesk'
        lines = party.turn(connection, 'm1', view(connection, [HESK]), 'Come with me, Hesk.', DAY, NOW, Dice(1),
                           agents={'hesk'}, choices={'hesk': True})
        assert lines == ['Hesk Aldane agrees to come along with the character, from now on, of their own will.']
        party.leave(connection, 'hesk')
        # Bonded, so a Program mind would come: their no stands.
        bonds.forge(connection, 'hesk', 'Hesk Aldane', 'sworn', NOW)
        assert 'by their own choice' in party.turn(connection, 'm2', view(connection, [HESK]), 'Join us, Hesk?', DAY,
                                                   NOW, Dice(100), agents={'hesk'}, choices={'hesk': False})[0]
        assert party.keys(connection) == set()
        # No answer (the agent failed): Dungeon's rule decides, and the bond brings them.
        party.turn(connection, 'm3', view(connection, [HESK]), 'Join us, Hesk?', DAY, NOW, Dice(1), agents={'hesk'})
        assert party.keys(connection) == {'hesk'}
        party.leave(connection, 'hesk')
        # Wary and unbonded, nobody asks them: they won't, whatever they would have said.
        met(connection, 'ilse', 'Ilse Brand')
        feelings.change(connection, 'ilse', {'trust': -1})
        assert party.askable(connection, view(connection, [ILSE]), 'Come with me, Ilse.') is None
        assert "won't come along" in party.turn(connection, 'm4', view(connection, [ILSE]), 'Come with me, Ilse.',
                                               DAY, NOW, Dice(100), agents={'ilse'}, choices={'ilse': True})[0]
        # Parting is not asking.
        assert party.askable(connection, view(connection, [HESK]), 'Go home, Hesk.') is None
