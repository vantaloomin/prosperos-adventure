"""Today's turn as the round loop's steps (adventure/rounds/telling.py) with the party's Resolve beside it, and roll
overrides from the GM view (adventure/rounds/overrides.py)."""
import asyncio

import pytest
from conftest import narrator, tell
from test_rounds_play import ok, rows, seated, steps  # noqa: F401 - the steps fixture

from adventure import chapters
from adventure.database import decode
from adventure.rounds import engine, play, queue, resolve
from adventure.rounds.contract import Declaration, State
from adventure.rounds.draft import Draft


@pytest.fixture
def hesk_threatens(steps):  # noqa: F811 - the fixture imported above
    async def declare(turn):
        if turn.snapshot.seat('hesk') is not None:
            turn.draft.declare(Declaration('hesk', 'I threaten the innkeeper.'))
    engine.register(State.DECLARING, 'declare', declare)


def result_of(client, turn_id=None):
    row = rows(client, 'SELECT * FROM round_turns ORDER BY created_at DESC, rowid DESC LIMIT 1')[0]
    return row, Draft.of(decode(row['draft'])).result


def test_a_players_line_and_an_agents_act_resolve_in_one_turn(client, connected, hesk_threatens):
    seated(client, 'hesk', human='you')
    told = tell(client, 'I look around the market.', 'telling-0001')
    assert told['reply']['status'] == 'complete'
    row, result = result_of(client)
    assert row['state'] == 'committed'
    hesk = [roll for roll in result.rolls if roll['actor'] == 'hesk']
    assert [(roll['kind'], roll['stat']) for roll in hesk] == [('threaten', 'Resolve')]
    assert [(item['actor'], item['kind']) for item in rows(client, 'SELECT * FROM round_rolls')] == [
        ('hesk', 'threaten')]
    # The narrator still tells the player's line as today.
    assert narrator(client.app.state.provider)['messages'][-1]['content'].endswith('I look around the market.')


def test_a_campaign_with_no_agents_resolves_only_the_players_line(client, connected, steps):  # noqa: F811
    told = tell(client, 'I try to pick the lock of the back door.', 'telling-0002')
    assert told['reply']['status'] == 'complete'
    _, result = result_of(client)
    assert {roll['kind'] for roll in result.rolls} == {resolve.LINE}
    assert rows(client, 'SELECT * FROM round_rolls') == []


def test_an_override_changes_one_roll_logs_it_marks_the_turn_and_flags_the_passage(client, connected,
                                                                                   hesk_threatens):
    seated(client, 'hesk', human='you')
    told = tell(client, 'I look around the market.', 'telling-0003')
    row, result = result_of(client)
    position = next(index for index, roll in enumerate(result.rolls) if roll['actor'] == 'hesk')
    was = result.rolls[position]['band']
    band = 'critical_failure' if was != 'critical_failure' else 'critical_success'
    done = ok(client.post(f"/api/rounds/turns/{row['id']}/rolls/{position}/override",
                          json={'band': band, 'reason': 'Hesk would never manage that.'}))
    assert (done['override']['from_band'], done['override']['to_band']) == (was, band)
    assert 'override' in done['turn']['marks']
    _, result = result_of(client)
    assert result.rolls[position]['band'] == band and result.brief.outcomes[position].endswith(
        f"{'Critical failure' if band == 'critical_failure' else 'Critical success'}.")
    assert rows(client, 'SELECT band FROM round_rolls')[0]['band'] == band
    flags = decode(rows(client, 'SELECT flags FROM story_messages WHERE id=?', (told['reply']['id'],))[0]['flags'])
    assert any('A roll was overridden' in why for flag in flags for why in flag['why'])


def test_rolls_stand_in_ironman(client, connected, hesk_threatens):
    seated(client, 'hesk', human='you')
    tell(client, 'I look around the market.', 'telling-0004')
    row, _ = result_of(client)
    with client.app.state.database.connect(write=True) as connection:
        chapters.set_ironman(connection, True)
    response = client.post(f"/api/rounds/turns/{row['id']}/rolls/0/override", json={'band': 'success', 'reason': 'x'})
    assert response.status_code == 409


def test_an_ambiguous_move_waits_for_the_answer_and_tells_the_line_as_meant(client, connected, steps):  # noqa: F811
    seated(client, 'hesk', 'mara', human='you')

    async def present(turn):
        turn.snapshot.present = ['you', 'hesk', 'mara']
    engine.register(State.GATHERING, 'present', present)
    told = tell(client, 'I punch him in the jaw.', 'telling-0005')
    assert told['reply'] is None
    state = client.app.state
    with state.database.connect() as connection:
        turn_id = queue.head(connection)
    row = rows(client, 'SELECT * FROM round_turns WHERE id=?', (turn_id,))[0]
    assert row['state'] == State.AWAITING_USER
    assert decode(row['draft'])['awaiting']['line'] == 'Who do you mean: Hesk or Mara?'
    asyncio.run(play.reply(state, turn_id, 'you', {'kind': 'reply', 'text': 'Hesk'}))
    row, result = result_of(client)
    assert row['state'] == 'committed'
    replies = rows(client, "SELECT * FROM story_messages WHERE reply_to=? AND role='narrator'",
                   (told['message']['id'],))
    assert [reply['status'] for reply in replies] == ['complete']
    assert any('meaning Hesk' in roll['action'] or roll['kind'] == resolve.LINE for roll in result.rolls)
