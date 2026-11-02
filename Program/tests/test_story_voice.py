"""Their voice stays theirs: lines the narration gave someone, shown to the narrator at later meetings
(dungeon/story_people.py). Ported from Prospero's Companion 1.0."""
from datetime import date, timedelta

from conftest import Chunk

from dungeon import story, story_people

ANNA = {'key': 'anna', 'name': 'Anna', 'full': 'Anna Bell'}
TOM = {'key': 'tom', 'name': 'Tom', 'full': 'Tom Reed'}


def ok(response):
    assert response.status_code == 200, response.text
    return response.json()


def test_a_quote_is_theirs_when_its_paragraph_names_only_them():
    reply = ('Anna sets the glass down hard. "You came back, after everything you swore to the magistrate?"\n\n'
             'Anna and Tom trade a look. "Nobody leaves this town twice and lives to boast of it," one says.\n\n'
             '"I told her I would pay the debt by midsummer," you say to Tom.\n\n'
             'Tom shrugs. "Fine."\n\n'
             '"Everyone in the Heartwood knows the price of a broken oath," Tom says at last.')
    found = story_people.heard([ANNA, TOM], reply)
    assert found == {'anna': ['You came back, after everything you swore to the magistrate?'],
                     'tom': ['Everyone in the Heartwood knows the price of a broken oath,'.rstrip(',')]}


def test_lines_are_kept_once_and_shown_only_from_earlier_meetings(client):
    day = date(2026, 3, 2)
    with client.app.state.database.connect(write=True) as connection:
        story_people.meet(connection, ANNA, 'baltimore', '2026-03-02T10:00:00Z', day)
        story_people.hear(connection, 'anna', ['You came back, after everything you swore to me?'] * 2, day)
        row = story_people.known(connection)['anna']
        assert story_people.voice_text(row) == '', 'said today: the recent story already shows it'
        later = day + timedelta(days=3)
        story_people.meet(connection, ANNA, 'baltimore', '2026-03-05T10:00:00Z', later)
        story_people.hear(connection, 'anna', ['Keep your coin, stranger, I have no use for it.'], later)
        row = story_people.known(connection)['anna']
    assert len(row['voice']) > 0
    shown = story_people.voice_text(row)
    assert '"You came back, after everything you swore to me?"' in shown and 'Keep your coin' not in shown
    assert shown.count('You came back') == 1 and 'never reuse these' in shown


def test_the_narrator_hears_how_someone_sounded_before(client, clock, provider):
    ok(client.put('/api/connection', json={'base_url': 'http://127.0.0.1:1234/v1', 'model': 'local-model'}))
    for _hour in range(48):
        with client.app.state.database.connect() as connection:
            data = story.city_data(connection, 'baltimore')
            moment = story.local_moment(data, clock.now())
            busy = next(((place, people) for place in data['places']
                         if (people := story.present(connection, data, place['id'], moment))), None)
        if busy:
            break
        clock.instant = clock.now() + timedelta(hours=1)
    place, people = busy
    ok(client.put('/api/story/scene', json={'city_id': 'baltimore', 'place_id': place['id']}))
    them = people[0]['sheet']
    line = 'Nobody pours a second drink for a stranger who will not give his name'
    provider.replies = [[Chunk(f'{them["name"]} leans on the counter. "{line}."'), Chunk('', 'stop')]]
    ok(client.post('/api/story/messages', json={'text': 'I lean on the counter.', 'client_id': 'voice-0001'}))
    with client.app.state.database.connect() as connection:
        assert story_people.known(connection)[them['key']]['voice'] != '[]'
    # A day on, still there or not, the narrator is told how they sounded when they come up.
    clock.instant = clock.now() + timedelta(days=1)
    ok(client.put('/api/story/scene', json={'city_id': 'baltimore', 'place_id': place['id']}))
    with client.app.state.database.connect() as connection:
        row = story_people.known(connection)[them['key']]
    today = story.local_moment(data, clock.now()).date().isoformat()
    assert f'"{line}."' not in story_people.remembered(row), 'not before the day is over'
    assert f'"{line}."' in story_people.remembered(row, today)
