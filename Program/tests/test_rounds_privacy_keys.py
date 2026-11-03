"""Seats keyed by story_people key reach their package facts (adventure/rounds/context.py "Keys"): a met notable through
the cast id on their town sheet, the human through the persona taken at the start."""
import asyncio

from test_combat import kingswood

from adventure import story, story_people, timeline, world_data
from adventure.rounds import context, engine, seats
from adventure.rounds.contract import Mind


def test_a_met_notable_and_the_players_persona_map_to_their_package_ids(client, connected, app):
    kingswood(client, 'reeves-hall')
    database = app.state.database
    with database.connect(write=True) as connection:
        data = story.city_data(connection, 'kingswood')
        aldous = next(sheet for sheet in story.townsfolk.at_place(data, 'reeves-hall')
                      if sheet.get('notable') == 'aldous-marr')
        story_people.meet(connection, aldous, 'kingswood', database.now(), story.datetime(2026, 10, 21).date())
        seats.set_seat(connection, aldous['key'], aldous['full'], database.now(), mind=Mind.AGENT)
        seats.set_seat(connection, 'you', 'Agna', database.now(), mind=Mind.HUMAN)

    async def gathered():
        turn = await engine.begin(app.state, timeline.ROOT, 1)
        await engine.steps_of(turn, engine.State.GATHERING)
        return turn
    turn = asyncio.run(gathered())
    assert turn.snapshot.settings['package_ids'] == {aldous['key']: 'aldous-marr', 'you': 'agna-holt'}
    secret = next(fact['text'] for fact in world_data.facts('vallarith') if fact['known_to'] == ['aldous-marr'])
    with database.connect() as connection:
        own = context.agent(connection, turn.snapshot, turn.draft, aldous['key'])
        writer = context.writer(connection, turn.snapshot, turn.draft)
    assert secret[:40] in own and 'Role:' in own
    assert secret[:40] not in writer
