"""Walking an interior (dungeon/delving.py): in, room to room, locks, traps, searching, foes, out; and seeded
interiors for rolled hex sites."""
import pytest
from conftest import Chunk, tell
from test_hexes import out_in_the_wild, site_hexes, vallarith
from test_inventory import begin

from dungeon import combat, delving, hexes, interiors, timeline
from dungeon.world.schema import Interior


class Dice:
    """Every check's d100 shows 95 (`good`) or 5, and every other die its highest or lowest."""

    def __init__(self, good: bool = True):
        self.good = good

    def randint(self, low, high):
        if high == 100:
            return 95 if self.good else 5
        return high if self.good else low

    def choice(self, items):
        return items[0]


GOOD, BAD = Dice(True), Dice(False)


def ok(response):
    assert response.status_code == 200, response.text
    return response.json()


def say(client, provider, text: str, client_id: str) -> dict:
    provider.replies = [[Chunk('On they go.'), Chunk('', 'stop')]]
    return tell(client, text, client_id)


def at_the_keep(client, app):
    begin(client)
    with app.state.database.connect(write=True) as connection:
        connection.execute("UPDATE story_scene SET city_id='vallarith-road', place_id='abandoned-keep' WHERE id=1")


def where(app) -> dict | None:
    with app.state.database.connect() as connection:
        return delving.inside(connection)


def put_in(app, room: str, previous: str | None = None):
    with app.state.database.connect(write=True) as connection:
        connection.execute("INSERT INTO story_interior (id, interior, room, previous, moves) "
                           "VALUES (1, 'abandoned-keep', ?, ?, 0)", (room, previous))
        delving.mark_room(connection, 'abandoned-keep', room, visited=1)


def test_going_in_moving_by_a_way_out_and_back_and_coming_out(client, connected, provider, app):
    at_the_keep(client, app)
    app.state.dice = GOOD
    say(client, provider, 'I go inside the keep.', 'delve-0001')
    assert where(app)['room'] == 'broken-gate'
    told = provider.requests[-1]['system']
    assert 'The character goes into The Abandoned Keep.' in told and 'They are in the broken gate' in told
    assert 'Ways out they can see: a low door in the gate passage; an open way; the way back outside.' in told
    # The gatehouse's gnolls roll to notice the character as they come in; a good roll and they have not.
    say(client, provider, 'I take the low door.', 'delve-0002')
    assert where(app)['room'] == 'gatehouse'
    assert "The 2 Haggoth's gnolls here have not seen the character." in provider.requests[-1]['system']
    say(client, provider, 'I go back the way I came.', 'delve-0003')
    assert where(app)['room'] == 'broken-gate'
    assert 'a low door in the gate passage to the gatehouse' in provider.requests[-1]['system']
    shown = ok(client.get('/api/story'))['interior']
    assert [(room['id'], room['here']) for room in shown['rooms']] == [('broken-gate', True), ('gatehouse', False)]
    assert {'between': ['broken-gate', 'gatehouse'], 'kind': 'door', 'to_known': True} in shown['passages']
    say(client, provider, 'I walk back outside.', 'delve-0004')
    assert where(app) is None
    assert 'comes back out of The Abandoned Keep' in provider.requests[-1]['system']
    assert ok(client.get('/api/story'))['interior'] is None


def test_foes_that_notice_the_character_start_a_fight_and_a_fight_won_clears_the_room(client, connected, provider,
                                                                                         app):
    at_the_keep(client, app)
    put_in(app, 'broken-gate')
    app.state.dice = BAD
    say(client, provider, 'I take the low door.', 'delve-0001')
    with app.state.database.connect() as connection:
        fight = combat.fight(connection)
        assert fight and "gnoll" in fight['foes'][0]['name']
        assert delving.inside(connection)['fighting'] == 'gatehouse'
    with app.state.database.connect(write=True) as connection:
        combat.save_fight(connection, None)
        delving.fought(connection, False, True)
        assert delving.rooms_state(connection, 'abandoned-keep')['gatehouse']['cleared']
        assert delving.room_foe(connection) is None


def test_a_locked_way_wants_a_roll_and_a_failed_one_leaves_the_character_where_they_were(client, connected, provider,
                                                                                        app):
    at_the_keep(client, app)
    put_in(app, 'cold-hall')
    with app.state.database.connect(write=True) as connection:
        delving.mark_room(connection, 'abandoned-keep', 'cold-hall', hazard_met=1)
    app.state.dice = BAD
    say(client, provider, 'I go down the worn steps behind the hearth.', 'delve-0001')
    assert where(app)['room'] == 'cold-hall'
    assert 'is locked, and stays locked' in provider.requests[-1]['system']
    app.state.dice = GOOD
    say(client, provider, 'I try the steps again.', 'delve-0002')
    assert where(app)['room'] == 'cellars'
    with app.state.database.connect() as connection:
        assert delving.ways_state(connection, 'abandoned-keep')[frozenset(('cold-hall', 'cellars'))]['opened']


def test_searching_finds_the_hidden_way_and_what_is_lying_there(client, connected, provider, app):
    at_the_keep(client, app)
    put_in(app, 'cellars')
    app.state.dice = GOOD
    say(client, provider, 'I search the cellars for anything hidden.', 'delve-0001')
    told = provider.requests[-1]['system']
    assert 'They find a hidden way out: a cistern wall that is a door.' in told
    assert 'They find and take:' in told
    assert 'a cistern wall that is a door' in told.split('Ways out they can see:')[1]
    with app.state.database.connect() as connection:
        assert {row['item_id'] for row in connection.execute('SELECT item_id FROM story_inventory')} >= {'lamp-oil', 'salt'}
    # The way found is trapped, and the vault beyond has a hazard: both are rolled going through.
    app.state.dice = GOOD
    say(client, provider, 'I go through the cistern door.', 'delve-0002')
    assert where(app)['room'] == 'ley-vault'
    told = provider.requests[-1]['system']
    assert 'gets past it' in told and 'touch the seam without being taken by it' in told


def test_going_back_a_line_puts_the_character_back_in_the_room_they_were_in(client, connected, provider, app):
    assert {'story_interior', 'story_interior_rooms', 'story_interior_ways'} <= set(timeline.SAVED)
    at_the_keep(client, app)
    app.state.dice = GOOD
    say(client, provider, 'I go inside the keep.', 'delve-0001')
    second = say(client, provider, 'I take the open way.', 'delve-0002')
    assert where(app)['room'] == 'ward-court'
    ok(client.post('/api/story/back', json={'message_id': second['message']['id']}))
    assert where(app)['room'] == 'broken-gate'


def test_a_rolled_site_has_the_same_inside_every_time_and_each_site_its_own():
    board = hexes.Grid(vallarith(), 'fixed')
    ruins = [board.site(at) for at in [*site_hexes(board, True), *site_hexes(board, False)]
             if board.site(at)['kind'] in ('ruin', 'cave', 'lair', 'battlefield')][:6]
    assert ruins
    made = []
    for site in ruins:
        site = site | {'map': 'vallarith', 'world': 'vallarith'}
        first = delving.generated('fixed', 'vallarith', site)
        assert first == delving.generated('fixed', 'vallarith', site)
        Interior.model_validate(first)
        assert first['rooms'][0]['id'] == first['entrance'] == 'way-in' and first['at']['site'] == delving.site_id(site)
        made.append(first)
    assert len({tuple(room['name'] for room in item['rooms']) for item in made}) > 1
    other_seed = delving.generated('other', 'vallarith', ruins[0] | {'map': 'vallarith', 'world': 'vallarith'})
    assert other_seed['id'] == made[0]['id']


def test_low_horror_keeps_dreadful_foes_out_of_a_rolled_inside():
    site = {'map': 'vallarith', 'world': 'vallarith', 'q': 3, 'r': 4, 'kind': 'cave', 'name': 'the long cave',
            'text': 'A cave.'}
    for seed in range(40):
        made = delving.generated(str(seed), 'vallarith', site | {'levels': {'horror': 0}})
        assert not any(foe.get('horror') for room in made['rooms'] for foe in room.get('foes', []))


def test_a_found_ruin_out_in_the_wild_can_be_gone_into(client, connected, provider, app):
    begin(client)
    board = hexes.Grid(vallarith(), 'fixed')
    at = next(at for at in site_hexes(board, True) if board.site(at)['kind'] == 'ruin')
    out_in_the_wild(app, at)
    with app.state.database.connect(write=True) as connection:
        hexes.find_site(connection, board, at, board.site(at))
    app.state.dice = GOOD
    say(client, provider, 'I go in through the doorway.', 'delve-0001')
    inside = where(app)
    assert inside and inside['room'] == 'way-in' and inside['site']['q'] == at[0]
    assert 'They are in the broken doorway' in provider.requests[-1]['system']
    # And searching inside searches the room, not the hex.
    say(client, provider, 'I search the place.', 'delve-0002')
    assert 'The character searches the broken doorway' in provider.requests[-1]['system']


@pytest.mark.parametrize('text, moving', [('I take the stairs down', True), ('I search the room', True),
                                          ('I talk to the gnoll', False), ('I leave', True)])
def test_which_lines_move_inside(text, moving):
    assert delving.moving(text) is moving


def test_the_keep_is_entered_from_its_stop():
    assert interiors.entered_from(world='vallarith', city='vallarith-road', place='abandoned-keep')['id'] == 'abandoned-keep'
