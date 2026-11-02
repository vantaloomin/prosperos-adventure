"""Scaling and tiers (dungeon/tiers.py): the character's tier, the work that comes to them and the world's tiers."""
from datetime import datetime

import pytest
from conftest import tell
from test_inventory import begin
from test_travel import Road, ok, reply

from dungeon import factions, happenings, jobs, quests, tiers

NOW = datetime(1290, 5, 1, 12)


@pytest.fixture
def hiring(monkeypatch):
    monkeypatch.setattr(factions, 'ACTIVE', True)


def offer(connection, *hundreds, looking=False):
    return jobs.offer(connection, 'vallarith', 'kingswood', 'kingswood', 150, {'symbol': 'cr.'}, NOW, Road(*hundreds),
                      looking=looking)


def test_the_track_climbs_the_ladder_within_the_arc(app):
    with app.state.database.connect(write=True) as connection:
        tiers.begin(connection, 'vallarith')
        assert tiers.tier(connection, 'vallarith') == 1
        assert tiers.earn(connection, 'vallarith', 11) == ''
        assert tiers.earn(connection, 'vallarith', 1).startswith("The character's renown rises: Regional, a name "
                                                                 'along the Cyrel road.')
        # Grounded stops at Regional, however much they earn; epic starts at Realm.
        tiers.begin(connection, 'vallarith', 'grounded', 'fast')
        tiers.earn(connection, 'vallarith', 500)
        assert tiers.tier(connection, 'vallarith') == 2
        tiers.begin(connection, 'vallarith', 'epic', 'slow')
        assert tiers.tier(connection, 'vallarith') == 3
        # A slow burn needs twice the track.
        tiers.earn(connection, 'vallarith', 159)
        assert tiers.tier(connection, 'vallarith') == 3
        tiers.earn(connection, 'vallarith', 1)
        assert tiers.tier(connection, 'vallarith') == 4


def test_the_player_picks_the_arc_at_the_start_and_sees_it_in_words(client):
    ok(client.put('/api/story/scene', json={'city_id': 'kingswood', 'place_id': 'pell-provisions'}))
    ok(client.delete('/api/story'))
    assert ok(client.get('/api/story/start'))['arc'] == {'arc': 'classic', 'pace': 'steady', 'hand': 'guiding'}
    ok(client.post('/api/story/start', json={'premade_id': 'agna-holt', 'arc': 'epic', 'pace': 'fast'}))
    tier = ok(client.get('/api/story'))['tier']
    assert tier == {'tier': 'Realm', 'words': 'a name at court in Cyrel', 'track': 'Renown', 'arc': 'epic',
                    'pace': 'fast'}
    ok(client.put('/api/settings', json={'show_odds': True}))
    assert ok(client.get('/api/story'))['tier'] == tier | {'points': 0, 'next': 40}


def test_work_comes_at_the_characters_tier_with_a_rare_stretch(app, hiring):
    with app.state.database.connect(write=True) as connection:
        tiers.begin(connection, 'vallarith')
        assert 'deserter from Bastion' in offer(connection, 50, 50)[0]
        quest = connection.execute("SELECT title, tier FROM story_quests WHERE kind='job'").fetchone()
        assert quest['tier'] == 1
        # A stretch: one tier up, with a warning; never two.
        stretched = offer(connection, 1, 50)
        assert stretched[-1].startswith('Those who know say this one is beyond the character: Regional work')
        tiers_offered = {row['tier'] for row in connection.execute("SELECT tier FROM story_quests WHERE kind='job'")}
        assert tiers_offered == {1, 2}
        for _ in range(10):
            offer(connection, 1, 1)
        assert 3 not in {row['tier'] for row in connection.execute('SELECT tier FROM story_quests')}


def test_lower_work_comes_only_to_those_who_look_for_it(app, hiring):
    with app.state.database.connect(write=True) as connection:
        tiers.begin(connection, 'vallarith', 'epic')
        # At Realm, only Realm work comes unasked.
        assert 'sealed terms carried into Adlmyr' in offer(connection, 50, 1)[0]
        assert offer(connection, 50, 1) == []
        assert "a feller's debt collected" in offer(connection, looking=True)[0]
    assert jobs.seeking('Anyone hiring? I need work.') and not jobs.seeking('I walk to the mill.')


def test_work_done_earns_more_above_the_character(app):
    with app.state.database.connect(write=True) as connection:
        tiers.begin(connection, 'vallarith')
        at = quests.create(connection, 'job', 'kingswood', 'At', 'hook', 'truth', 'missed', None, tier=1)
        quests.end(connection, at, 'done', 'Done.')
        assert tiers.state(connection, 'vallarith')['points'] == 4
        above = quests.create(connection, 'job', 'kingswood', 'Above', 'hook', 'truth', 'missed', None, tier=2)
        quests.end(connection, above, 'done', 'Done.')
        assert tiers.state(connection, 'vallarith')['points'] == 20 and tiers.tier(connection, 'vallarith') == 2
        # An oath kept earns no renown.
        oath = quests.create(connection, 'oath', 'kingswood', 'Oath', 'hook', '', '', None)
        quests.end(connection, oath, 'done', 'Kept.')
        assert tiers.state(connection, 'vallarith')['points'] == 20


def test_foes_come_at_the_regions_tier_or_from_an_enemy_above_it(app):
    spec = happenings.FOES['bandits']
    with app.state.database.connect(write=True) as connection:
        tiers.begin(connection, 'vallarith')
        cyrel = happenings.where('kingswood', 'pell-provisions')
        assert cyrel['tier'] == 1 and tiers.foe(connection, cyrel, spec, 1) == (spec, '')
        brynwyr = cyrel | {'tier': 3}
        foe, sent = tiers.foe(connection, brynwyr, spec, 1)
        assert (foe['vitality'], foe['resolve'], foe['weapon'], sent) == (14, 12, 1, '')
        assert tiers.warning(connection, brynwyr).startswith('Signs on the way warn the character: this is Realm '
                                                             'country, and they are Local.')
        assert tiers.warning(connection, cyrel) == ''
        # An enemy of the realm sends its own.
        factions.shift(connection, factions.find('vallarith', 'kingdom-of-cyrel'), -4)
        foe, sent = tiers.foe(connection, cyrel, spec, 1)
        assert foe['vitality'] == 14 and sent.startswith('They were sent by The Kingdom of Cyrel')


def test_the_narrator_knows_the_characters_standing(client, connected, provider):
    begin(client)
    reply(provider, 'Pell nods.')
    tell(client, 'I nod back.', 'story-0001')
    assert ("## The character's standing (kept by the game)\n- Renown: Local, known on their own street."
            in provider.requests[-1]['system'])
