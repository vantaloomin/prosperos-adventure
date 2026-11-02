"""The director v0 (dungeon/director.py): arcs and the spine, threads, the hand, the GM note and nemeses."""
from datetime import datetime, timedelta

import pytest
from conftest import tell
from test_travel import Road, ok, reply

from dungeon import director, factions, jobs, quests, record, tiers

NOW = datetime(1290, 5, 1, 12)


@pytest.fixture
def directed(monkeypatch):
    monkeypatch.setattr(director, 'ACTIVE', True)


def start(client, hand='guiding'):
    ok(client.put('/api/story/scene', json={'city_id': 'kingswood', 'place_id': 'pell-provisions'}))
    ok(client.delete('/api/story'))
    return ok(client.post('/api/story/start', json={'premade_id': 'agna-holt', 'hand': hand}))


def note(connection, drama='uneasy', node='kingswood', people=(), now=NOW):
    return director.note(connection, 'vallarith', node, list(people), drama, now)


def test_the_campaign_starts_with_the_worlds_arcs_and_a_thread_for_each(client, app):
    start(client)
    with app.state.database.connect() as connection:
        assert set(director.arcs(connection)) == {'the-eight-pieces', 'the-long-border', 'the-failing-wards'}
        kinds = sorted((row['kind'], row['title']) for row in director.threads(connection))
        assert ('mystery', 'The Eight Pieces') in kinds and ('lead', 'The Heartwood contract') in kinds
        heartwood = connection.execute("SELECT arc_id, thread_id FROM story_quests WHERE id='the-heartwood-contract'"
                                       ).fetchone()
        assert heartwood['arc_id'] == 'the-eight-pieces' and heartwood['thread_id']
        # The character has come across none of the arcs yet.
        assert director.journal(connection) == []
    assert ok(client.get('/api/story/journal'))['threads'] == []


def test_biting_on_an_arc_heats_its_threads_and_makes_it_the_spine(client, app):
    start(client)
    with app.state.database.connect(write=True) as connection:
        director.touch(connection, 'vallarith', 'I ask about the Heartwood.', 'social', 'm1', 'x')
        director.touch(connection, 'vallarith', 'I ask about the Heartwood again.', 'social', 'm1', 'x')
        hot = director.threads(connection)[0]
        assert hot['heat'] == director.TOUCH and hot['bite'] == 1
        assert director.journal(connection)[0]['title'] == 'The Eight Pieces'
        for n in range(director.COMMIT):
            director.touch(connection, 'vallarith', 'The roots of the grove.', 'quiet', f'm{n + 2}', 'x')
        assert director.state(connection)['spine_id'] == 'the-eight-pieces'
        # A far harder turn toward another arc promotes it.
        for n in range(director.PROMOTE * (director.COMMIT + 1) + 1):
            director.touch(connection, 'vallarith', 'Deserters from Bastion.', 'quiet', f'b{n}', 'x')
        assert director.state(connection)['spine_id'] == 'the-long-border'
        assert director.state(connection)['recent'] == ['quiet'] * director.RECENT


def test_with_no_bite_the_world_default_spine_comes_after_three_chapters(client, app):
    start(client)
    with app.state.database.connect(write=True) as connection:
        for n in range(director.CHAPTER_LINES * director.SPINE_CHAPTERS + 1):
            director.touch(connection, 'vallarith', 'I wait.', 'quiet', f'm{n}', 'x')
        assert director.state(connection)['spine_id'] == 'the-eight-pieces'


def test_arcs_move_on_their_own_clocks_and_the_hand_decides_how_they_arrive(client, app, directed):
    start(client)
    with app.state.database.connect(write=True) as connection:
        director.advance(connection, 'vallarith', NOW, NOW + timedelta(days=1), 'x', Road(1, 99, 99))
        assert director.arcs(connection)['the-eight-pieces']['stage'] == 1
        assert any('infernal ink' in row['text'] and row['truth'] == 'world'
                   for row in record.entries(connection, known_only=False))
        # Regional, above a Local character: it reaches them as a rumor, never its fight; and only once.
        text = note(connection)
        assert 'Due (The Eight Pieces): A clerk from Cyrel is buying drinks' in text and 'never its fight' in text
        assert 'Due (' not in note(connection)
        tiers.begin(connection, 'vallarith', 'epic')
        director.advance(connection, 'vallarith', NOW, NOW + timedelta(days=1), 'x', Road(99, 1, 99))
        text = note(connection)
        assert "Due (The Long Border): Bastion's deserters flood Kingswood" in text
        assert 'come looking for the character' in text
    start(client, 'soft')
    with app.state.database.connect(write=True) as connection:
        director.advance(connection, 'vallarith', NOW, NOW + timedelta(days=1), 'x', Road(1, 99, 99))
        assert director.arcs(connection)['the-eight-pieces']['stage'] == 1 and 'Due (' not in note(connection)


def test_the_note_follows_the_tension_curve_and_plants_a_seed_once(client, app, directed):
    start(client)
    with app.state.database.connect(write=True) as connection:
        director.touch(connection, 'vallarith', 'A fight.', 'crisis', 'm1', 'x')
        text = note(connection)
        assert 'let this scene breathe' in text
        assert 'Seed, if it fits the scene: A root cut at the edge of the grove bleeds' in text
        assert 'Seed' not in note(connection)
        director.touch(connection, 'vallarith', 'The Heartwood.', 'quiet', 'm2', 'x')
        for n in range(3):
            director.touch(connection, 'vallarith', 'I wait.', 'quiet', f'q{n}', 'x')
        assert 'Pressure: the story has gone slack. Bring' in note(connection, 'eventful')
        assert 'Pressure' not in note(connection, 'quiet')
        # The line the note pressed counts as pressure, so the next lines do not all ask again.
        pressed = note(connection, 'eventful')
        assert director.scene_kind([], [], [{'key': 'x'}], [pressed]) == 'pressure'
        assert director.scene_kind([], [], [{'key': 'x'}], ['- Pressure: none. After that, let it breathe']) == 'social'
        director.touch(connection, 'vallarith', 'I wait.', 'pressure', 'p1', 'x')
        assert 'Pressure' not in note(connection, 'eventful')
        # The spine's antagonist is near in Kingswood once play has bitten on it.
        assert "Nearby: Gannet & Pryce's agent" in note(connection)


def test_a_job_may_link_into_an_arc_and_leave_a_seed(client, app, monkeypatch):
    start(client)
    monkeypatch.setattr(factions, 'ACTIVE', True)
    with app.state.database.connect(write=True) as connection:
        arc_id, tie = director.link(connection, 'vallarith', Road(1))
        assert arc_id and tie[0]['kind'] == 'clue'
        assert director.link(connection, 'vallarith', Road(99)) == (None, [])
        jobs.offer(connection, 'vallarith', 'kingswood', 'kingswood', 150, {'symbol': 'cr.'}, NOW, Road(50, 1, 1))
        job = next(quest for quest in quests.rows(connection) if quest['kind'] == 'job')
        assert job['arc_id'] == arc_id and job['ties'][-1]['kind'] == 'clue' and job['thread_id']
        quests.end(connection, job['id'], 'done', 'Done.', 'x')
        assert not any(thread['quest_id'] == job['id'] for thread in director.threads(connection))


def test_a_foe_who_got_away_becomes_a_nemesis_and_comes_back(client, app, directed):
    start(client)
    with app.state.database.connect(write=True) as connection:
        director.history(connection, [('fled', 'road bandit 2'), ('horror', 'x')], NOW, 'x', Road(1))
        nemesis = connection.execute('SELECT * FROM story_nemeses').fetchone()
        assert nemesis['name'] == 'the road bandit who got away' and nemesis['remembers'] == 'Vitality'
        assert any(row['kind'] == 'grudge' for row in director.journal(connection))
        for n in range(5):
            director.touch(connection, 'vallarith', 'I wait.', 'quiet', f'q{n}', 'x')
        assert 'comes back' not in note(connection, now=NOW + timedelta(days=1))
        assert 'Pressure: the road bandit who got away comes back, with a plan' in \
            note(connection, now=NOW + timedelta(days=director.NEMESIS_DAYS))
        # Killed on the page, they stay dead.
        director.history(connection, [('kill', 'road bandit 1')], NOW, 'x', Road(99))
        assert connection.execute('SELECT status FROM story_nemeses').fetchone()['status'] == 'dead'
        director.history(connection, [('robbed', 'Corin Ashby')], NOW, 'x', Road(1))
        assert connection.execute("SELECT name FROM story_nemeses WHERE status='alive'").fetchone()['name'] == \
            'Corin Ashby'


def test_every_turn_carries_the_hidden_note_and_touches_the_notebook(client, connected, provider, app, directed):
    start(client, 'firm')
    reply(provider, 'Pell talks about the Heartwood.')
    tell(client, 'I ask Pell about the Heartwood contract.', 'story-0001')
    assert "## The game master's note (hidden" in provider.requests[-1]['system']
    with app.state.database.connect() as connection:
        assert director.state(connection)['hand'] == 'firm'
        assert director.arcs(connection)['the-eight-pieces']['bite'] == 1
    assert ok(client.get('/api/story/journal'))['threads'][0]['seen'].startswith('Something about the Heartwood')
