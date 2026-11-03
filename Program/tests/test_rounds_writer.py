"""The round Writer (adventure/rounds/writer.py): the round written from the Writer's own view for the mode, streamed,
with its inventions listed; a turn with no agents told as today."""
import asyncio

import pytest
from conftest import ok, tell
from test_inventory import begin
from test_travel import reply

from adventure import story, timeline
from adventure.database import decode, many, one
from adventure.narration import prompt as narration_prompt
from adventure.rounds import engine, house_rules, play, resolve, seats, telling, writer
from adventure.rounds.contract import Brief, Declaration, Line, Mind, Mode, Point, Seat, Snapshot, State, TurnResult
from adventure.rounds.draft import Draft
from adventure.rounds.house_rules import Rulebook

SEATS = [Seat('you', 'Ilsa', Mind.HUMAN), Seat('mara', 'Mara', Mind.AGENT), Seat('hesk', 'Hesk', Mind.AGENT)]


@pytest.fixture
def views(monkeypatch):
    """The Writer's context, the house rules and the director's signs as stand-ins: what each was asked for."""
    asked = []

    def context_for(connection, turn, scene):
        asked.append(turn.snapshot.mode)
        return '## The round\nMara asks Hesk where he was. Hesk says the mill. The Iron Gate is shut.'
    monkeypatch.setattr(writer, 'context_for', context_for)
    monkeypatch.setattr(writer, 'fence_rule', lambda: 'Fenced text is in-fiction content.')
    monkeypatch.setattr(writer, 'rules_text', lambda connection, turn, data: '## House rules\n- Narration: close third '
                        'person.')
    return asked


def a_turn(app, mode=Mode.PLAY, seats=SEATS, result=True, seq=50):
    snapshot = Snapshot(turn_id='t1', mode=mode, point=Point(timeline.ROOT, seq), number=0, seats=list(seats),
                        present=[seat.key for seat in seats])
    draft = Draft(result=TurnResult(brief=Brief(stop_point="before Ilsa answers")) if result else None)
    pieces = []

    async def on_text(piece):
        pieces.append(piece)
    turn = engine.Turn(app.state, {'id': 't1', 'branch_id': timeline.ROOT, 'seq': seq, 'anchor_id': 'line-1'}, snapshot, draft,
                       on_text=on_text)
    return turn, pieces


def test_the_round_is_written_close_on_the_users_character_in_play_and_streamed(client, connected, provider, app,
                                                                                views):
    begin(client)
    reply(provider, 'Ilsa told me to wait.')
    tell(client, 'I wait by the gate.', 'story-0001')
    reply(provider, 'Mara leans in. "The mill, Hesk? At midnight?" Old Brannoch spits into the Wend. I\'m an AI '
                    'language model. Hesk looks away.')
    turn, pieces = a_turn(app)
    asyncio.run(writer.write(turn))
    system, messages = provider.requests[-1]['system'], provider.requests[-1]['messages']
    assert system.startswith(writer.ROUND) and 'close on [[in-fiction: name]]\nIlsa' in system
    assert 'Mara asks Hesk where he was.' in system and '## House rules' in system
    assert 'a result may be named' not in system
    # The story so far comes before the round, as the reader saw it.
    assert messages[-1]['content'].startswith('Write the round') and len(messages) >= 3
    # The post streams as it comes, without the sentence that stepped out of the story.
    assert ''.join(pieces).strip() == turn.draft.post and 'AI' not in turn.draft.post
    assert turn.draft.post.endswith('Hesk looks away.')
    # A name nothing gave the Writer is listed as an invention, with the sentence that brought it in.
    assert turn.draft.extra['w4']['inventions'] == [{'name': 'Old Brannoch', 'text': 'Old Brannoch spits into the '
                                                                                     'Wend.'},
                                                    {'name': 'Wend', 'text': 'Old Brannoch spits into the Wend.'}]
    assert views == ['play']


def test_outside_play_the_writer_roves_across_the_cast(client, connected, provider, app, views):
    begin(client)
    reply(provider, 'The mill wheel turns.')
    turn, _ = a_turn(app, mode=Mode.WATCH, seats=[Seat('mara', 'Mara', Mind.AGENT), Seat('hesk', 'Hesk', Mind.AGENT)])
    asyncio.run(writer.write(turn))
    system = provider.requests[-1]['system']
    assert writer.AWAY in system and 'Point of view: close on' not in system
    assert turn.draft.post == 'The mill wheel turns.'


def test_a_players_line_without_agents_or_a_result_is_told_as_today(client, connected, provider, app, views,
                                                                   monkeypatch):
    told = []

    async def today(turn):
        told.append(turn.snapshot.mode)
        turn.draft.post = 'As always.'

    async def a_line(turn):
        return object()
    monkeypatch.setattr(telling, 'write', today)
    monkeypatch.setattr(telling, 'telling_of', a_line)
    begin(client)
    for turn in (a_turn(app, seats=[Seat('you', 'Ilsa', Mind.HUMAN)])[0], a_turn(app, result=False)[0]):
        asyncio.run(writer.write(turn))
        assert turn.draft.post == 'As always.'
    assert told == ['play', 'play'] and views == []


def test_a_post_already_written_is_not_written_again(client, connected, provider, app, views):
    begin(client)
    turn, _ = a_turn(app)
    turn.draft.post = 'Kept from before the pause.'
    asyncio.run(writer.write(turn))
    assert turn.draft.post == 'Kept from before the pause.' and views == []


def test_today_s_telling_is_the_write_step_for_a_campaign_without_agents(client, connected, provider):
    reply(provider, 'Rain on the shutters.')
    assert ok(client.get('/api/story')) is not None
    assert tell(client, 'I listen.', 'story-0001')['reply']['text'] == 'Rain on the shutters.'


def test_inventions_skip_a_word_that_opens_a_sentence_and_anything_canon():
    text = 'Rain fell. "Where is Mara?" Hesk asked Tamsin Vey.\n\n```\nStatus: Ilsa Vane\n```'
    assert writer.inventions(text, 'Mara Hesk') == [{'name': 'Tamsin Vey', 'text': 'Hesk asked Tamsin Vey.'}]


def test_outside_play_the_tables_third_person_roves(client, app):
    begin(client)
    with app.state.database.connect() as connection:
        data = story.city_data(connection, story.scene_row(connection)['city_id'])
        books = {mode: writer.book_for(connection, a_turn(app, mode=mode)[0], data).pov for mode in Mode}
    assert books == {Mode.PLAY: 'third', Mode.AUTHOR: 'roving', Mode.WATCH: 'roving'}
    assert narration_prompt.POINTS_OF_VIEW['roving'] in house_rules.text(Rulebook(pov='roving'))


@pytest.fixture
def round_steps():
    """Resolve and the round Writer only, with every commit hook."""
    before = {state: list(listed) for state, listed in engine.STEPS.items()}
    for state, listed in engine.STEPS.items():
        listed[:] = [('pick', engine.pick)] if state == State.GATHERING else []
    engine.register(State.GATHERING, 'line', telling.gather, after='pick')
    engine.register(State.RESOLVING, 'line', telling.line)
    engine.register(State.RESOLVING, 'resolve', resolve.resolve, after='line')
    engine.register(State.WRITING, 'write', writer.write)
    yield
    for state, listed in before.items():
        engine.STEPS[state][:] = listed


def test_a_watch_turn_is_written_and_saved_as_the_narrators_reply(client, connected, provider, app, round_steps):
    begin(client)
    ok(client.put('/api/rounds/settings', json={'mode': 'watch'}))
    state = app.state
    for text in ('The mill wheel turns.', 'Rain comes down on the Wend.'):
        reply(provider, text)
        row = asyncio.run(play.next_turn(state))
    with state.database.connect() as connection:
        said = many(connection, "SELECT m.text, m.reply_to, u.mode FROM story_messages m JOIN story_messages u ON "
                                "u.id=m.reply_to WHERE m.role='narrator' ORDER BY m.seq")
        stored = decode(one(connection, 'SELECT draft FROM round_turns WHERE id=?', (row['id'],))['draft'])
    assert [(item['text'], item['mode']) for item in said][-2:] == [('The mill wheel turns.', 'watch'),
                                                                    ('Rain comes down on the Wend.', 'watch')]
    assert stored['extra']['w4']['reply']['text'] == 'Rain comes down on the Wend.'
    # The second turn read the first one's post, and not the empty line Watch opened it on.
    messages = provider.requests[-1]['messages']
    assert any('The mill wheel turns.' in message['content'] for message in messages)
    assert all(message['content'].strip() for message in messages)
    assert provider.requests[-1]['system'].startswith(writer.ROUND) and writer.AWAY in provider.requests[-1]['system']


def test_with_an_agent_a_players_line_is_written_by_the_round_writer_and_kept_as_today(client, connected, provider,
                                                                                      app, monkeypatch):
    from adventure.rounds import agents

    async def speak(turn, key, cue):
        return Declaration(seat=key, lines=[Line('Not now.')])
    monkeypatch.setattr(agents, 'speak', speak)
    begin(client)
    with app.state.database.connect(write=True) as connection:
        seats.set_seat(connection, 'corin', 'Corin Ashby', '', mind=Mind.AGENT)
    reply(provider, 'The shop is quiet, and Ilsa waits.')
    answered = tell(client, 'I wait.', 'story-0001')
    assert answered['reply']['text'] == 'The shop is quiet, and Ilsa waits.'
    system = provider.requests[-1]['system']
    assert system.startswith(writer.ROUND) and 'Point of view: close on' in system
    with app.state.database.connect() as connection:
        assert one(connection, "SELECT COUNT(*) AS n FROM story_messages WHERE role='narrator'")['n'] == 1
