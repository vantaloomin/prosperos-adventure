"""Rest (dungeon/rest.py): safe and risky nights, precautions, a fight in the dark, time, food and mending."""
from datetime import datetime

from conftest import narrator as last_narration
from conftest import tell
from test_inventory import begin
from test_travel import Road, clock_at, ok, reply

from dungeon import combat, rest, travel


def out_in_the_badlands(client):
    begin(client)
    ok(client.put('/api/story/scene', json={'city_id': 'vallarith-road', 'place_id': 'abandoned-keep'}))


def local_time(client) -> datetime:
    return datetime.fromisoformat(ok(client.get('/api/story'))['scene']['local_time'])


def test_a_night_runs_to_the_morning_when_it_starts_in_the_evening():
    assert rest.first_night(datetime(2026, 10, 22, 18, 0)) == 13 * 60
    assert rest.first_night(datetime(2026, 10, 22, 23, 30)) == 7 * 60 + 30
    # Bedding down in the small hours or by day is eight hours.
    assert rest.first_night(datetime(2026, 10, 22, 3, 0)) == rest.NIGHT_MINUTES
    assert rest.first_night(datetime(2026, 10, 22, 13, 0)) == rest.NIGHT_MINUTES
    assert rest.resting('I spend the night at the bunkhouses.')


def test_what_counts_as_a_rest_and_how_long():
    assert rest.resting('I go to bed.') and rest.resting('We make camp under the wall.')
    assert rest.resting('I rest for a week at the inn.') and not rest.resting('I sleep with her.')
    assert not rest.resting('I rest my hand on the hilt.')
    assert rest.nights_in('I rest for three days.') == 3 and rest.nights_in('I rest for a week.') == 7
    assert rest.nights_in('I sleep three nights at the Wayhouse to heal.') == 3
    assert rest.nights_in('I sleep.') == 1 and rest.nights_in('I rest for 90 days.') == rest.MOST_NIGHTS


def test_a_night_in_town_is_safe_and_passes_the_night(client, connected, provider, app):
    begin(client)
    app.state.dice = Road(1)
    before, local = clock_at(app), local_time(client)
    reply(provider, 'Morning.')
    tell(client, 'I go to bed.', 'story-0001')
    assert (clock_at(app) - before).total_seconds() == rest.first_night(local) * 60
    narrator = provider.requests[-1]['system']
    assert '## The rest' in narrator and 'rests for the night, somewhere safe' in narrator
    assert ok(client.get('/api/story'))['fight']['fight'] is None


def test_precautions_cut_the_odds_of_a_bad_night():
    # The Badlands are high danger: 50 in 100 a night, and 15 with a watch kept and the camp hidden.
    assert rest.plan('vallarith-road', 'abandoned-keep', 'I make camp.', Road(20))['interrupted']
    careful = rest.plan('vallarith-road', 'abandoned-keep', 'I make camp off the road with no fire and keep watch.',
                        Road(20))
    assert careful['precautions'] == ['watch', 'hidden'] and careful['interrupted'] is None
    assert rest.plan('kingswood', 'felled-oak', 'I go to bed.', Road(1)) == {
        'nights': 1, 'safe': True, 'precautions': [], 'interrupted': None}


def test_raiders_in_the_night_start_a_fight_and_end_the_rest(client, connected, provider, app, monkeypatch):
    out_in_the_badlands(client)
    with app.state.database.connect(write=True) as connection:
        combat.set_condition(connection, 2)
    monkeypatch.setattr(travel, 'pick', lambda entries, rng: next(entry for entry in entries if 'raiders' in str(entry)))
    # The night turns something up (10 of 50), the raiders, and the Luck roll (a step harder asleep) fails.
    app.state.dice = Road(10, 15)
    before = clock_at(app)
    reply(provider, 'Hooves in the dark.')
    tell(client, 'I make camp in the ruins.', 'story-0001')
    story = ok(client.get('/api/story'))
    assert {foe['name'] for foe in story['fight']['fight']['foes']} <= {f'Unguruk raider {n}' for n in (1, 2, 3)}
    assert (clock_at(app) - before).total_seconds() == rest.CUT_SHORT_MINUTES * 60
    narrator = provider.requests[-1]['system']
    assert 'Unguruk raiders ride down' in narrator and 'The rest ends here' in narrator
    assert 'with no precautions' in narrator and 'mend' not in narrator.split('## The rest')[1]
    # No rest with a fight on.
    reply(provider, 'No sleep.')
    tell(client, 'I lie down and sleep.', 'story-0002')
    assert 'cannot rest with a fight on' in last_narration(provider)['system']


def test_days_out_in_the_open_eat_from_the_pack_and_hunger_slows_mending(client, connected, provider, app):
    out_in_the_badlands(client)
    with app.state.database.connect(write=True) as connection:
        combat.set_condition(connection, 3)
        connection.execute("INSERT INTO story_inventory (id, city_id, item_id, qty) VALUES ('b', 'kingswood', 'bread', 1)")
    app.state.dice = Road(99, 99, 99)
    before, local = clock_at(app), local_time(client)
    reply(provider, 'Three cold days.')
    tell(client, 'I lie up in the keep and rest for three days, keeping watch.', 'story-0001')
    assert (clock_at(app) - before).total_seconds() == (2 * rest.DAY_MINUTES + rest.first_night(local)) * 60
    narrator = provider.requests[-1]['system'].split('## The rest')[1]
    assert 'for 3 nights out in the open, keeping watch' in narrator and '1 hungry day' in narrator
    # Three nights, one of them hungry: two count toward Wounded's four.
    assert 'still wounded: 2 more nights' in narrator
    with app.state.database.connect() as connection:
        assert connection.execute("SELECT qty FROM story_inventory WHERE id='b'").fetchone()[0] == 0
    # Telling it again sleeps no more.
    slept = clock_at(app)
    reply(provider, 'Again.')
    ok(client.post('/api/story/retry'))
    assert clock_at(app) == slept
