"""A round with no player's line (Author, Watch, Next in Play) does what a player's line does once its post is up:
the director gives the Writer its note and hears the post, and fact extraction follows, so a quest can end there
(adventure/rounds/writer.py `committed`, adventure/story.py `after_round`; docs/spec.md, code and model boundary
follow-ups)."""
import asyncio

from test_judged import continuity
from test_quests import begin_in_kingswood, ok
from test_rounds_writer import round_steps  # noqa: F401 - the fixture
from test_travel import reply

from adventure import director, record, story
from adventure.database import decode, one
from adventure.rounds import play


def watching(client):
    ok(client.put('/api/rounds/settings', json={'mode': 'watch'}))


def test_a_watch_round_reads_facts_from_its_post_alone_and_can_end_a_quest(client, connected, provider, app,
                                                                         round_steps):  # noqa: F811
    begin_in_kingswood(client)
    continuity(client)
    watching(client)
    state = app.state
    provider.replies = [[*chunks('Agna tears the Heartwood notice down: the Guild has withdrawn the contract.')],
                        [*chunks('{"facts": [], "quests": [{"id": "the-heartwood-contract", "status": "done", '
                                 '"outcome": "The Guild withdrew the contract."}]}')]]
    row = asyncio.run(play.next_turn(state))
    asyncio.run(story.settled(state))
    with state.database.connect() as connection:
        quest = one(connection, "SELECT status FROM story_quests WHERE id='the-heartwood-contract'")
    assert quest['status'] == 'done'
    # The Continuity model read the post alone: Watch's opening line is empty and is not "the player".
    [asked] = [request['messages'][-1]['content'] for request in provider.requests
               if request['system'].startswith(record.EXTRACT[:40])]
    assert asked.startswith('The narrator: Agna tears the Heartwood notice down') and 'The player:' not in asked
    report = ok(client.get(f"/api/story/turns/{row['id']}/report"))
    [judged] = report['judged']
    assert judged['kind'] == 'quest' and judged['label'].startswith('The Heartwood contract is done')
    ok(client.post(f"/api/story/turns/{row['id']}/judged/{judged['id']}/undo"))
    with state.database.connect() as connection:
        assert one(connection, "SELECT status FROM story_quests WHERE id='the-heartwood-contract'")['status'] == 'open'


def test_an_author_rounds_nudge_is_never_read_as_the_players_line(client, connected, provider, app):
    begin_in_kingswood(client)
    with app.state.database.connect(write=True) as connection:
        line = story.add(connection, 'now', 'user', 'Have the factor betray her.', story.scene_row(connection))
        connection.execute("UPDATE story_messages SET mode='author' WHERE id=?", (line['id'],))
        post = story.add(connection, 'now', 'narrator', 'The factor smiles.', story.scene_row(connection),
                         reply_to=line['id'])
        assert record.turn_of(connection, post['id']) == ('', 'The factor smiles.')
    assert record.turn_text('', 'The factor smiles.') == 'The narrator: The factor smiles.'


def test_a_round_with_no_players_line_gets_the_directors_note_and_moves_its_curve(client, connected, provider, app,
                                                                               round_steps, monkeypatch):  # noqa: F811
    monkeypatch.setattr(director, 'ACTIVE', True)
    begin_in_kingswood(client, 'pell-provisions')
    watching(client)
    state = app.state
    with state.database.connect(write=True) as connection:
        director.touch(connection, 'vallarith', 'A fight.', 'crisis', 'earlier', 'x')
        lines = director.state(connection)['lines']
    reply(provider, 'The shop is quiet; the Heartwood notice curls in the damp.')
    row = asyncio.run(play.next_turn(state))
    system = provider.requests[0]['system']
    assert "The game master's note" in system and 'let this scene breathe' in system
    assert 'Seed, if it fits the scene:' in system
    with state.database.connect() as connection:
        stored = decode(one(connection, 'SELECT draft FROM round_turns WHERE id=?', (row['id'],))['draft'])
        kept = director.state(connection)
    assert any('let this scene breathe' in text for text in stored['extra']['w4']['noted'])
    # The director heard the post, as it hears a player's line: one line more, and the scene's kind on the curve.
    assert kept['lines'] == lines + 1 and kept['last_message'] == row['anchor_id']
    assert kept['recent'][-1] in ('quiet', 'social')


def chunks(text):
    from adventure.providers.chat import Chunk
    return [Chunk(text), Chunk('', 'stop')]


def test_a_players_line_in_a_round_with_agents_keeps_the_directors_note(client, connected, provider, app,
                                                                         monkeypatch):
    from conftest import tell

    from adventure.rounds import agents, seats, writer
    from adventure.rounds.contract import Declaration, Mind
    monkeypatch.setattr(director, 'ACTIVE', True)

    async def speak(turn, key, cue):
        return Declaration(seat=key)
    monkeypatch.setattr(agents, 'speak', speak)
    begin_in_kingswood(client, 'pell-provisions')
    with app.state.database.connect(write=True) as connection:
        seats.set_seat(connection, 'corin', 'Corin Ashby', '', mind=Mind.AGENT)
        director.touch(connection, 'vallarith', 'A fight.', 'crisis', 'earlier', 'x')
    reply(provider, 'The shop is quiet, and Agna waits.')
    tell(client, 'I wait.', 'story-0001')
    [system] = [request['system'] for request in provider.requests if request['system'].startswith(writer.ROUND)]
    assert "The game master's note" in system and 'let this scene breathe' in system
