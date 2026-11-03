"""What the fact extraction model judged after a turn, each with an undo (adventure/judged.py; docs/spec.md, code and
model boundary follow-ups)."""
from conftest import tell
from test_bonds import met
from test_quests import begin_in_kingswood, ok, reply

from adventure import feelings, judged, quests


def continuity(client):
    profiles = ok(client.get('/api/models'))['profiles']
    ok(client.put('/api/models/routes', json={'job': 'continuity', 'profile_id': profiles[0]['id']}))


def last_turn(app) -> str:
    with app.state.database.connect() as connection:
        return connection.execute("SELECT id FROM round_turns WHERE state='committed' ORDER BY rowid DESC"
                                  ).fetchone()[0]


def test_a_quest_the_model_ended_is_in_the_turn_report_and_undone_whole(client, connected, app, provider):
    begin_in_kingswood(client)
    continuity(client)
    with app.state.database.connect() as connection:
        settled = ('story_tier', 'story_reputation', 'story_grades')
        before = {table: rows for table, rows in judged.snapshot(connection).items() if table in settled}
        heartwood = connection.execute("SELECT * FROM story_quests WHERE id='the-heartwood-contract'").fetchone()
        assert heartwood['status'] == 'open'
    provider.replies = [reply('The factor tears the notice down.'),
                        reply('{"facts": [], "quests": [{"id": "the-heartwood-contract", "status": "done", '
                              '"outcome": "The Guild withdrew the contract."}], "oaths": [{"to": "the factor", '
                              '"text": "To keep quiet about the arrow.", "days": 3}]}')]
    tell(client, 'I show the factor the warden arrow.', 'story-0001')
    turn_id = last_turn(app)
    report = ok(client.get(f'/api/story/turns/{turn_id}/report'))
    assert [(item['kind'], item['label'], item['undone']) for item in report['judged']] == [
        ('quest', 'The Heartwood contract is done: The Guild withdrew the contract.', False),
        ('oath', 'An oath to the factor: To keep quiet about the arrow.', False)]
    quest, oath = report['judged']
    assert ok(client.get('/api/story/journal'))['quests'][0]['status'] == 'done'

    # Undoing the ending reopens the quest and takes back what it settled; the oath stays.
    undone = ok(client.post(f"/api/story/turns/{turn_id}/judged/{quest['id']}/undo"))
    assert undone['undone'] is True
    with app.state.database.connect() as connection:
        after = {table: rows for table, rows in judged.snapshot(connection).items() if table in settled}
        assert after == before
        assert dict(connection.execute("SELECT * FROM story_quests WHERE id='the-heartwood-contract'").fetchone()) \
            == dict(heartwood) | {'known': 1}
        assert connection.execute("SELECT status FROM story_threads WHERE quest_id='the-heartwood-contract'"
                                  ).fetchone()['status'] == 'open'
        assert [row['title'] for row in quests.rows(connection, 'open')
                if row['kind'] == 'oath'] == ['An oath to the factor']
    assert [item['undone'] for item in ok(client.get(f'/api/story/turns/{turn_id}/report'))['judged']] == [True, False]
    assert client.post(f"/api/story/turns/{turn_id}/judged/{quest['id']}/undo").status_code == 409

    # The oath, undone, is gone too.
    ok(client.post(f"/api/story/turns/{turn_id}/judged/{oath['id']}/undo"))
    with app.state.database.connect() as connection:
        assert not [row for row in quests.rows(connection) if row['kind'] == 'oath']
    assert client.post(f'/api/story/turns/{turn_id}/judged/nothing/undo').status_code == 404


def test_undoing_a_feeling_moves_it_back_by_what_the_model_moved_and_keeps_later_moves(client, app):
    begin_in_kingswood(client)
    with app.state.database.connect(write=True) as connection:
        met(connection)
        feelings.change(connection, 'hesk', {'trust': 1})
        judging = judged.Judging(connection, 'reply-1', 'now')
        with judging.change('feeling', "Hesk Aldane's feelings: trust +2"):
            feelings.change(connection, 'hesk', {'trust': 2}, 'You stood by them.')
        with judging.change('dark', 'Nothing at all'):
            pass
        [row] = connection.execute('SELECT kind, changes FROM judged_changes').fetchall()
        assert row['kind'] == 'feeling'
        # A later turn moves trust again, then the model's move is undone: the later move stays.
        feelings.change(connection, 'hesk', {'trust': -1})
        judged.reverse(connection, judged.decode(row['changes']))
        assert feelings.of(dict(connection.execute("SELECT * FROM story_people WHERE key='hesk'").fetchone()))['trust'] == 0
