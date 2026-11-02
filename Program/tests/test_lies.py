"""NPCs lie to keep what they hide, and the character's insight is rolled (dungeon/lies.py)."""
from conftest import Chunk, tell

from dungeon import lies, record

NOW, DAY = '2026-10-01T12:00:00Z', '2026-10-01'


class Dice:
    def __init__(self, natural):
        self.natural = natural

    def randint(self, low, high):
        return self.natural if (low, high) == (1, 100) else low

    def choice(self, items):
        return items[0]


def begin(client):
    client.put('/api/story/scene', json={'city_id': 'kingswood', 'place_id': 'felled-oak'})
    client.delete('/api/story')
    client.post('/api/story/start', json={'premade_id': 'agna-holt'})


MARR = {'sheet': {'key': 'marr', 'full': 'Aldous Marr', 'name': 'Aldous', 'role': 'reeve', 'occupation': 'reeve',
                  'notable': 'aldous-marr',
                  'wants': 'to get the first crews past the stones before the week is out, and nobody asking '
                           'questions'}}
ASH = {'sheet': {'key': 'ash', 'full': 'Pell Ash', 'name': 'Pell', 'role': 'baker', 'occupation': 'baker',
                 'wants': 'a quiet life'}}


def view(people, known=None, data=None):
    return {'people': people, 'known': known or {}, 'data': data or {'notables': []}}


def entries(connection, kind):
    return [row['text'] for row in record.entries(connection, known_only=False) if row['kind'] == kind]


def test_someone_with_something_to_hide_lies_and_insight_may_catch_it(app, client):
    begin(client)
    with app.state.database.connect(write=True) as connection:
        assert lies.turn(connection, 'm0', view([MARR]), 'I nod to the reeve.', DAY, NOW) == []
        assert lies.turn(connection, 'm0', view([ASH]), 'Pell, who was here last night?', DAY, NOW) == []
        believed = lies.turn(connection, 'm1', view([MARR, ASH]), 'I ask Aldous who is paying for the crews.', DAY,
                             NOW, Dice(1))
        assert believed[0].startswith('Aldous Marr lies to keep hidden what they are after') and \
            'no tell' in believed[1]
        assert any('lied to the player' in text for text in entries(connection, 'secret'))
        # Kept with the line, and the same story the rest of the day.
        assert lies.turn(connection, 'm1', view([MARR]), 'whatever', DAY, NOW, Dice(100)) == believed
        again = lies.turn(connection, 'm2', view([MARR]), 'Are you sure?', DAY, NOW, Dice(100))
        assert again[0].startswith('Aldous Marr keeps to the same story') and 'no tell' in again[0]
        caught = lies.turn(connection, 'm3', view([MARR]), 'Are you sure?', '2026-10-02', NOW, Dice(100))
        assert 'sees through it' in caught[1]
        # Someone who trusts the character tells them the truth.
        assert lies.turn(connection, 'm4', view([MARR], {'marr': {'trust': 3}}), 'Who pays?', '2026-10-03', NOW,
                         Dice(1)) == []


def test_a_notable_secret_or_a_job_s_truth_is_hidden_too(app, client):
    begin(client)
    data = {'notables': [{'id': 'pell', 'secret': 'she sells to the wardens'}]}
    baker = {'sheet': ASH['sheet'] | {'notable': 'pell'}}
    with app.state.database.connect(write=True) as connection:
        assert lies.hidden(connection, data, baker) == 'she sells to the wardens'
        connection.execute("INSERT INTO story_quests (id, city_id, title, status, kind, hook, truth, giver) "
                           "VALUES ('q', 'kingswood', 'A job', 'open', 'job', 'Carry it', 'It is stolen', 'Pell Ash')")
        assert lies.hidden(connection, {'notables': []}, ASH) == 'the truth of the work they gave: It is stolen'


def test_the_narrator_hears_the_lie(client, connected, provider, app, monkeypatch):
    begin(client)
    asked = []

    def lying(connection, message_id, view, text, day, now, rng=None):
        asked.append(text)
        return ['Corin Ashby lies to keep hidden who pays him.']

    monkeypatch.setattr(lies, 'turn', lying)
    provider.replies = [[Chunk('He smiles.'), Chunk('', 'stop')]]
    tell(client, 'Who is buying the Heartwood timber?', 'story-0001')
    assert asked == ['Who is buying the Heartwood timber?']
    assert '## A lie (decided by the game; never say outright that it is a lie)\n- Corin Ashby lies' in \
        provider.requests[-1]['system']


def test_a_near_miss_leaves_the_character_uneasy(app, client):
    begin(client)
    with app.state.database.connect(write=True) as connection:
        lines = lies.turn(connection, 'm1', view([MARR]), 'Who pays for the crews, Aldous?', DAY, NOW, Dice(45))
        assert "doesn't sit right" in lines[1] and 'without giving the lie away' in lines[1]
        assert any("didn't sit right" in text for text in entries(connection, 'fact'))
