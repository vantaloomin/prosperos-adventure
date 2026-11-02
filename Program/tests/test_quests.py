"""Quests and dangers v0 (dungeon/quests.py): deadlines on the story clock, and rolls in dangerous places."""
from datetime import datetime, timedelta

from conftest import Chunk, tell

from dungeon import quests, record


def ok(response):
    assert response.status_code == 200, response.text
    return response.json()


def reply(text):
    return [Chunk(text), Chunk('', 'stop')]


def begin_in_kingswood(client, place_id=None):
    ok(client.put('/api/story/scene', json={'city_id': 'kingswood', **({'place_id': place_id} if place_id else {})}))
    ok(client.delete('/api/story'))
    return ok(client.post('/api/story/start', json={'premade_id': 'agna-holt'}))


def test_every_adventure_names_real_places_and_quests_that_can_be_told():
    for path in quests.ADVENTURES.glob('*.json'):
        from dungeon.world import catalog
        data, adventure = catalog.city(path.stem), quests.adventure(path.stem)
        places = {place['id'] for place in data['places']}
        for quest in adventure['quests']:
            assert quest['title'] and quest['hook'] and quest['truth'] and set(quest['places']) <= places
            assert quest['missed'] or not quest['days']
        for danger in adventure['dangers']:
            assert danger['place'] in places and danger['threats'] and danger['difficulty'] in ('easy', 'normal', 'hard',
                                                                                                'very_hard', 'extreme')


def test_a_quest_starts_with_the_story_and_its_deadline_lands_on_the_story_clock(client, connected, app, provider):
    begin_in_kingswood(client)
    journal = ok(client.get('/api/story/journal'))
    # The player knows of the contract and how long is left; the wardens' eyes stay hidden.
    assert [(quest['title'], quest['left']) for quest in journal['quests']] == [('The Heartwood contract',
                                                                                 'about 7 days left')]
    provider.replies = [reply('The factor counts coins.')]
    tell(client, 'I read the contract on the green.', 'story-0001')
    narrator = provider.requests[-1]['system']
    assert '## What is happening' in narrator and 'Behind it: The Heartwood stands on a convergence' in narrator
    assert "The wardens' eyes (the player's character does not know of this yet)" in narrator

    # The week runs out.
    with app.state.database.connect(write=True) as connection:
        due = datetime.fromisoformat(connection.execute('SELECT at FROM story_clock').fetchone()[0]) + timedelta(minutes=3)
        connection.execute("UPDATE story_quests SET due_at=? WHERE id='the-heartwood-contract'", (due.isoformat(),))
    provider.replies = [reply('Smoke over the camp.')]
    tell(client, 'I ask the barman what the smoke is.', 'story-0002')
    journal = ok(client.get('/api/story/journal'))
    assert journal['quests'][0]['status'] == 'missed' and 'burned Cutters\' Camp' in journal['quests'][0]['outcome']
    assert journal['entries'][0]['subject'] == 'The Heartwood contract'
    assert 'The Heartwood contract is over (missed)' in provider.requests[-1]['system']


def test_the_continuity_model_says_when_a_turn_ended_a_quest(client, connected, app, provider):
    begin_in_kingswood(client)
    profiles = ok(client.get('/api/models'))['profiles']
    ok(client.put('/api/models/routes', json={'job': 'continuity', 'profile_id': profiles[0]['id']}))
    provider.replies = [reply('The factor tears the notice down.'),
                        reply('{"facts": [], "quests": [{"id": "the-heartwood-contract", "status": "done", '
                              '"outcome": "The Guild withdrew the contract."}, {"id": "nothing", "status": "done", '
                              '"outcome": "x"}]}')]
    tell(client, 'I show the factor the warden arrow.', 'story-0001')
    # A quest settled is a scene break too, so the chapter's summary is asked for after it.
    asked = next(request for request in reversed(provider.requests) if request['system'].startswith(record.EXTRACT))
    assert 'These quests are open:' in asked['system']
    quest = ok(client.get('/api/story/journal'))['quests'][0]
    assert (quest['status'], quest['outcome'], quest['left']) == ('done', 'The Guild withdrew the contract.', '')


class Unlucky:
    """Dice that always roll low, and the first threat."""

    def randint(self, low, high):
        return 20 if high == 100 else low

    def choice(self, items):
        return items[0]


def test_a_dangerous_place_rolls_every_turn_and_a_failure_brings_its_threat(client, connected, app, provider):
    begin_in_kingswood(client, 'the-heartwood')
    app.state.dice = Unlucky()
    provider.replies = [reply('The trees lean in.')]
    sent = tell(client, 'I look around.', 'story-0001')
    rolls = sent['message']['rolls'] if 'rolls' in sent['message'] else None
    narrator = provider.requests[-1]['system']
    assert 'come through the Heartwood unharmed' in narrator
    assert 'The ground hums, and for a moment they cannot remember which way the stones are.' in narrator
    assert rolls is None or rolls[-1]['stat'] == 'Luck'
    # Somewhere safe, nothing is rolled for the place.
    assert quests.danger_action('kingswood', 'felled-oak') is None


def test_a_vow_sworn_on_a_quest_is_that_quest_not_a_new_oath(client, app):
    # Playtest M4b, finding 5: "an oath to the wood under the stump" was filed beside the contract.
    begin_in_kingswood(client)
    now = datetime(2026, 10, 22, 9)
    with app.state.database.connect(write=True) as connection:
        oath = {'to': 'the wood under the stump', 'text': 'To see the contract stopped.', 'days': 6}
        kept = quests.vow(connection, 'kingswood', 'I swear an iron vow that the Heartwood contract will fail.', oath,
                          now)
        assert kept == 'the-heartwood-contract' and len(quests.rows(connection, 'open')) == 2  # with the wardens' eyes
        assert any('Swore to see The Heartwood contract through' in row['text'] for row in record.entries(connection))
        # An oath to someone, about something else, is its own.
        other = quests.vow(connection, 'kingswood', 'I promise Corin his money.', {'to': 'Corin', 'text': 'Pay Corin.',
                                                                                   'days': 3}, now)
        assert other.startswith('oath-')
