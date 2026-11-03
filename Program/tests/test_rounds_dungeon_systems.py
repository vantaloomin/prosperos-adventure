"""Dungeon's systems in agent play (docs/spec.md "Dungeon systems in agent play"): factions in an agent's goals, the
lead's travel line and splitting the party, lore timers counted in rounds, Ideas by mode, and the book export's
switch for motives and whispers."""
import asyncio
import copy
import json

import pytest
from test_rounds_modes import played, snapshot_of
from test_rounds_play import ok, rows, seated

from adventure import factions, lore, world_data
from adventure.rounds import declare, engine, play, timing, travelling
from adventure.rounds.contract import Declaration, Point, Seat, Snapshot, State


async def everyone(turn):
    """Everyone at the table is in the scene, as the foundation's 'present' would say of a party together."""
    turn.snapshot.present = [seat.key for seat in turn.snapshot.seats]


@pytest.fixture
def steps():
    """The agents' 'pick', the memory hook, and the travel and lore timing steps and hooks, whatever else registered."""
    before = {state: list(listed) for state, listed in engine.STEPS.items()}
    hooks, after = list(engine.COMMITS), dict(engine.AFTER)
    for listed in engine.STEPS.values():
        listed[:] = []
    engine.STEPS[State.GATHERING][:] = [('present', everyone), ('apart', travelling.elsewhere),
                                        ('pick', declare.pick), ('travel', travelling.gathered),
                                        ('lore_timers', timing.frozen)]
    engine.STEPS[State.REACTING][:] = [('split', travelling.split)]
    engine.COMMITS[:] = [('memory', engine.committed_memory), ('travel', travelling.committed),
                         ('lore_timers', timing.committed)]
    yield
    for state, listed in before.items():
        engine.STEPS[state][:] = listed
    engine.COMMITS[:] = hooks
    engine.AFTER.clear()
    engine.AFTER.update(after)


def declares(*declarations, post=''):
    async def step(turn):
        for declaration in map(copy.deepcopy, declarations):
            turn.draft.declare(declaration)
        turn.draft.post = post
    return step


def move(client, place):
    with client.app.state.database.connect(write=True) as connection:
        connection.execute("INSERT INTO story_scene (id, city_id, place_id, updated_at) VALUES (1, 'kingswood', ?, 'x') "
                           'ON CONFLICT(id) DO UPDATE SET place_id=excluded.place_id', (place,))


def party_of(client, *keys):
    with client.app.state.database.connect(write=True) as connection:
        for key in keys:
            connection.execute("INSERT INTO story_party (key, name, city_id, sheet, joined) VALUES "
                               "(?, ?, 'kingswood', '{}', 'x')", (key, key.title()))


# Factions -------------------------------------------------------------------------------------------------------------

def test_an_agent_knows_its_factions_aims_never_what_its_clocks_will_bring(client, monkeypatch):
    monkeypatch.setattr(world_data, 'person', lambda world, key: {'faction': 'kingdom-of-cyrel'} if key == 'hesk'
                        else {})
    snapshot = Snapshot('t', 'play', Point('first', 1), 0, seats=[Seat('you', 'Ilsa', 'human'), Seat('hesk', 'Hesk')],
                        settings={'world': 'vallarith'})
    with client.app.state.database.connect() as connection:
        lines = factions.known_to(connection, snapshot, 'hesk')
        assert factions.known_to(connection, snapshot, 'you') == []
        # The agent's own context takes them as its factions part (adventure/rounds/context.py).
        from adventure.rounds import context
        assert context.faction_lines(connection, snapshot, 'hesk') == lines
    assert lines[0].startswith('You belong to The Kingdom of Cyrel (realm): A stubborn fortress kingdom')
    assert 'Hold the Badlands line' in lines[1] and 'What it is working toward now: War levy.' in lines
    assert any(line.startswith('Its rivals: ') for line in lines) and lines[-1] == 'Ilsa is unknown to it.'
    cyrel = factions.find('vallarith', 'kingdom-of-cyrel')
    assert not any(clock['done'] in ' '.join(lines) for clock in cyrel['clocks'])


# Travel ---------------------------------------------------------------------------------------------------------------

def test_the_lead_proposes_and_an_agent_who_stays_splits_off_until_they_meet_again(client, steps):
    seated(client, 'mara', 'hesk', human='you')
    party_of(client, 'mara', 'hesk')
    ok(client.put('/api/rounds/mode', json={'mode': 'watch'}))
    move(client, 'pell-provisions')
    engine.register(State.DECLARING, 'declare', declares(
        Declaration('you', 'sets out for Eriane along the north road'), Declaration('mara', 'follows'),
        Declaration('hesk', 'stays behind at the provisioner, arms folded')))
    first = played(client)['turn']
    # In Watch the lead is the first seat, unless one is set.
    assert snapshot_of(client, first['id'])['settings']['travel']['lead'] == 'you'
    draft = json.loads(rows(client, 'SELECT draft FROM round_turns WHERE id=?', (first['id'],))[0]['draft'])
    assert draft['extra']['travel'] == {'line': 'sets out for Eriane along the north road', 'split': ['hesk'],
                                        'rejoined': []}
    with client.app.state.database.connect(write=True) as connection:
        here = engine.resumed(client.app.state, first['id']).point
        assert travelling.apart(connection, Point(here.branch, 10 ** 9)) == {
            'hesk': {'city_id': 'kingswood', 'place_id': 'pell-provisions'}}
    assert ok(client.put('/api/rounds/lead', json={'seat_key': 'mara'}))['lead'] == 'mara'
    assert client.put('/api/rounds/lead', json={'seat_key': 'nobody'}).status_code == 404
    # Elsewhere, Hesk stays apart; back where they parted, the party meets them again.
    move(client, 'the-oak-and-anchor')
    engine.register(State.DECLARING, 'declare', declares(Declaration('mara', 'looks around')))
    second = played(client, against=first['id'])['turn']
    held = snapshot_of(client, second['id'])['settings']['travel']
    assert held['lead'] == 'mara' and held['apart'] == ['hesk'] and held['rejoined'] == []
    assert 'hesk' not in snapshot_of(client, second['id'])['present']
    move(client, 'pell-provisions')
    third = played(client, against=second['id'])['turn']
    assert snapshot_of(client, third['id'])['settings']['travel']['rejoined'] == ['hesk']
    assert 'hesk' in snapshot_of(client, third['id'])['present']
    with client.app.state.database.connect() as connection:
        assert travelling.apart(connection, Point(timeline_branch(client), 10 ** 9)) == {}
        # Going back to before the split forgets it.
        assert travelling.apart(connection, engine.resumed(client.app.state, first['id']).point) == {}


def timeline_branch(client):
    from adventure import timeline
    with client.app.state.database.connect() as connection:
        return timeline.active(connection)


def test_no_travel_line_no_split_and_program_party_members_follow(client, steps):
    seated(client, 'mara', human='you')
    party_of(client, 'mara')
    ok(client.put('/api/rounds/seats/hesk', json={'name': 'Hesk', 'mind': 'program'}))
    ok(client.put('/api/rounds/mode', json={'mode': 'author'}))
    engine.register(State.DECLARING, 'declare', declares(Declaration('you', 'orders another round'),
                                                         Declaration('mara', 'stays where she is')))
    turn = played(client, nudge='')['turn']
    draft = json.loads(rows(client, 'SELECT draft FROM round_turns WHERE id=?', (turn['id'],))[0]['draft'])
    assert draft['extra']['travel']['line'] is None and draft['extra']['travel']['split'] == []
    assert rows(client, 'SELECT * FROM split_off') == []


# Lore timers ----------------------------------------------------------------------------------------------------------

def test_lore_timers_count_rounds_in_every_mode(client, steps):
    with client.app.state.database.connect(write=True) as connection:
        connection.execute("INSERT INTO lore_books (id, name, created_at) VALUES ('book', 'Book', 'x')")
        connection.execute("INSERT INTO lore_entries (id, book_id, position, text, keywords, sticky, cooldown) VALUES "
                           "('wyrm', 'book', 0, 'The wyrm sleeps under the hill.', '[\"wyrm\"]', 1, 2)")
    seated(client, 'mara')
    ok(client.put('/api/rounds/mode', json={'mode': 'watch'}))
    engine.register(State.DECLARING, 'declare', declares(post='Far off, the wyrm stirs in its sleep.'))
    first = played(client)['turn']
    assert snapshot_of(client, first['id'])['settings']['lore'] == {'line': 1, 'lingering': [], 'held': []}
    assert rows(client, 'SELECT * FROM lore_timers') == [{'entry_id': 'wyrm', 'active_until': 2, 'rest_until': 4}]
    engine.register(State.DECLARING, 'declare', declares(post='Quiet.'))
    ok(client.put('/api/rounds/mode', json={'mode': 'author'}))
    second = played(client, nudge='', against=first['id'])['turn']
    assert snapshot_of(client, second['id'])['settings']['lore']['lingering'] == ['wyrm']
    third = played(client, nudge='', against=second['id'])['turn']
    assert snapshot_of(client, third['id'])['settings']['lore'] == {'line': 3, 'lingering': [], 'held': ['wyrm']}


def test_a_timed_entrys_chance_is_seeded_by_branch_and_line(client):
    with client.app.state.database.connect(write=True) as connection:
        connection.execute("INSERT INTO lore_books (id, name, created_at) VALUES ('book', 'Book', 'x')")
        connection.execute("INSERT INTO lore_entries (id, book_id, position, text, keywords, chance) VALUES "
                           "('rare', 'book', 0, 'A rare thing.', '[\"rare\"]', 50)")
        rolls = [lore.round_timing(connection, line, 'first')['held'] for line in range(1, 30)]
        assert rolls == [lore.round_timing(connection, line, 'first')['held'] for line in range(1, 30)]
        assert ['rare'] in rolls and [] in rolls


# Ideas ----------------------------------------------------------------------------------------------------------------

def test_ideas_in_author_are_nudges_from_the_authors_view_and_watch_has_none(client, app, steps):
    seated(client, 'mara', human='you')
    ok(client.put('/api/rounds/mode', json={'mode': 'author'}))
    engine.register(State.DECLARING, 'declare', declares(Declaration('mara', 'counts the coins',
                                                                     motive='Skim a share for herself.')))
    played(client, nudge='')
    found = ok(client.post('/api/story/ideas'))
    assert found['mode'] == 'author' and 2 <= len(found['ideas']) <= 3
    from adventure import ideas
    with app.state.database.connect() as connection:
        view = ideas.author_view(connection, ideas.known_scene(connection, app.state.database))
    assert ('Mara', 'counts the coins / (motive) Skim a share for herself.') in view['moves']
    assert '[[in-fiction: Mara]]' in ideas.author_prompt(view)
    ok(client.put('/api/rounds/mode', json={'mode': 'watch'}))
    response = client.post('/api/story/ideas')
    assert response.status_code == 409 and response.json()['detail'] == 'Watch has no Ideas.'


def test_author_ideas_leave_out_motives_missed_in_play(client, app, steps):
    seated(client, 'mara', human='you')
    engine.register(State.DECLARING, 'declare', declares(Declaration('mara', 'smiles', motive='Rob them blind.')))
    asyncio.run(play.next_turn(app.state))
    ok(client.put('/api/rounds/mode', json={'mode': 'author'}))
    from adventure import ideas
    with app.state.database.connect() as connection:
        view = ideas.author_view(connection, ideas.known_scene(connection, app.state.database))
    assert view['moves'] == [('Mara', 'smiles')]


# The book -------------------------------------------------------------------------------------------------------------

def test_the_book_sets_motives_and_whispers_beside_the_post_only_when_asked(client, app, steps):
    seated(client, 'mara', human='you')
    ok(client.put('/api/rounds/mode', json={'mode': 'watch'}))

    async def writes(turn):
        from adventure import story
        turn.draft.declare(Declaration('mara', 'counts the coins', motive='Skim a share for herself.',
                                       whispers=[{'text': 'Keep quiet about the purse.', 'to': ['you']}]))
        with turn.database.connect(write=True) as connection:
            story.add(connection, turn.database.now(), 'narrator', 'Mara counts the coins by the fire.',
                      story.scene_row(connection))
    engine.register(State.WRITING, 'write', writes)
    played(client)
    plain = client.get('/api/story/export/book?format=md')
    assert plain.status_code == 200 and 'Unseen' not in plain.text and 'Mara counts the coins' in plain.text
    shown = client.get('/api/story/export/book?format=md&hidden=true').text
    assert ("Mara counts the coins by the fire.\n\n*Unseen: Mara's motive: Skim a share for herself.*\n\n"
            '*Unseen: Mara whispers to You: Keep quiet about the purse.*') in shown
    for kind in ('epub', 'pdf'):
        assert client.get(f'/api/story/export/book?format={kind}&hidden=true').status_code == 200
