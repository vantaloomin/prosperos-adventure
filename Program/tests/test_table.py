"""The Table (dungeon/table.py): each campaign plays by its own rules, which no longer follow the user between worlds."""
from dungeon import table

STATS = {'Mind': 12, 'Allure': 12, 'Resolve': 10, 'Vitality': 10, 'Essence': 8, 'Luck': 8}
ASH = {'name': 'Ash Ward', 'gender': 'nonbinary', 'age': 30, 'about': 'New in town, and broke.'}


def ok(response):
    assert response.status_code == 200, response.text
    return response.json()


def begin(client):
    return ok(client.post('/api/story/start', json={'persona': ASH, 'stats': STATS}))


def test_a_new_campaign_takes_the_worlds_tone_and_the_players_last_taste(client):
    rules = ok(client.get('/api/story/table'))
    assert rules == {'intensity': 'world', 'drama': 'world', 'injury_persistence': 'permanent', 'defeat': 'as_written',
                     'show_odds': False,
                     'roll_dice': False, 'show_adult_side': False, 'gm_view': False, 'cutaways': False,
                     'levels': None, 'veils': None, 'voice': 'world',
                     'pov': 'second', 'tense': 'present', 'length': 'short', 'shop_cash': 'finite',
                     'carry_limit': 'slots', 'clock': 'world', 'rule_text': 'on',
                     'leaving': 'anyone', 'politics': 'true_to_life'}
    begin(client)
    rules = ok(client.put('/api/story/table', json={'intensity': 'restrained', 'show_odds': True, 'roll_dice': True}))
    assert (rules['intensity'], rules['show_odds'], rules['roll_dice']) == ('restrained', True, True)
    assert ok(client.get('/api/story'))['table'] == rules
    # The dice show for this campaign; the next one starts with them shown too, but in the world's own tone.
    ok(client.delete('/api/story'))
    begin(client)
    rules = ok(client.get('/api/story/table'))
    assert (rules['intensity'], rules['show_odds'], rules['roll_dice']) == ('world', True, True)


def test_rules_stay_with_their_world(client):
    begin(client)
    ok(client.put('/api/story/table', json={'intensity': 'unflinching', 'gm_view': True}))
    first = ok(client.get('/api/worlds'))['world']
    made = ok(client.post('/api/worlds', json={'name': 'Somewhere else'}))
    ok(client.post(f"/api/worlds/{made['id']}/switch"))
    begin(client)
    elsewhere = ok(client.get('/api/story/table'))
    assert (elsewhere['intensity'], elsewhere['gm_view']) == ('world', True)
    ok(client.put('/api/story/table', json={'gm_view': False, 'drama': 'quiet'}))
    ok(client.post(f"/api/worlds/{first['id']}/switch"))
    back = ok(client.get('/api/story/table'))
    assert (back['intensity'], back['gm_view'], back['drama']) == ('unflinching', True, 'world')


def test_the_settings_route_still_sets_the_playing_campaigns_rule(client):
    begin(client)
    ok(client.put('/api/settings', json={'injury_persistence': 'none', 'show_odds': True}))
    rules = ok(client.get('/api/story/table'))
    assert (rules['injury_persistence'], rules['show_odds']) == ('none', True)
    assert ok(client.get('/api/story'))['injury_persistence'] == 'none'


def test_a_rule_set_before_the_campaign_begins_is_kept(client):
    ok(client.put('/api/story/table', json={'drama': 'merciless'}))
    begin(client)
    assert ok(client.get('/api/story/table'))['drama'] == 'merciless'


def test_a_campaign_from_before_the_table_keeps_the_rules_it_played_by(app):
    with app.state.database.connect(write=True) as connection:
        connection.execute("UPDATE workspace_settings SET intensity='mature', show_odds=1 WHERE id=1")
        connection.execute('INSERT INTO story_campaign (id, ironman) VALUES (1, 0)')
        table.adopt(connection)
        connection.execute("UPDATE workspace_settings SET intensity='restrained', show_odds=0 WHERE id=1")
        rules = table.rules(connection)
    assert (rules['intensity'], rules['show_odds']) == ('mature', True)


def test_session_zero_offers_presets_and_starts_the_campaign_by_its_rules(client):
    choices = ok(client.get('/api/story/start'))
    assert [preset['id'] for preset in choices['presets']] == ['as-written', 'gentler', 'harsher']
    assert choices['table']['intensity'] == 'world'
    gentler = choices['presets'][1]['rules']
    ok(client.post('/api/story/start', json={'persona': ASH, 'stats': STATS, 'table': {**gentler, 'show_odds': True}}))
    rules = ok(client.get('/api/story/table'))
    assert (rules['intensity'], rules['drama'], rules['injury_persistence'], rules['show_odds']) == \
        ('restrained', 'quiet', 'temporary', True)
    # What is shown is remembered for the next campaign; the tone is not.
    ok(client.delete('/api/story'))
    rules = ok(client.get('/api/story/start'))['table']
    assert (rules['intensity'], rules['show_odds']) == ('world', True)


def test_session_zero_sets_how_a_5e_defeat_goes(client):
    ok(client.post('/api/story/start', json={'persona': ASH, 'stats': STATS, 'table': {'defeat': 'by_aim'}}))
    assert ok(client.get('/api/story/table'))['defeat'] == 'by_aim'
    # A defeat is tone: the next campaign starts as written again.
    ok(client.delete('/api/story'))
    assert ok(client.get('/api/story/start'))['table']['defeat'] == 'as_written'


def test_a_new_campaign_is_told_in_close_third_past_and_the_player_can_change_it(client):
    # Before a campaign starts, Story mode speaks to the player as "you"; session zero offers a new campaign's format.
    assert ok(client.get('/api/story/start'))['table']['pov'] == 'third'
    begin(client)
    rules = ok(client.get('/api/story/table'))
    assert (rules['pov'], rules['tense'], rules['length']) == ('third', 'past', 'short')
    rules = ok(client.put('/api/story/table', json={'pov': 'first', 'tense': 'present', 'length': 'long'}))
    assert (rules['pov'], rules['tense'], rules['length']) == ('first', 'present', 'long')
    assert client.put('/api/story/table', json={'pov': 'fourth'}).status_code == 422


def test_a_format_chosen_at_session_zero_is_kept(client):
    ok(client.post('/api/story/start', json={'persona': ASH, 'stats': STATS, 'table': {'pov': 'second'}}))
    assert ok(client.get('/api/story/table'))['pov'] == 'second'


def test_the_narrator_is_told_the_format(app):
    from dungeon import story
    with app.state.database.connect(write=True) as connection:
        assert story.narration_format(connection).pov == 'second'
        table.begin(connection)
        assert story.narration_format(connection).text('Ash Ward').startswith(
            'Narration: close third person on Ash Ward, past tense')
