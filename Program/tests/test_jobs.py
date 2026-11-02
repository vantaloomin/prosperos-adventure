"""Jobs from factions' needs (dungeon/jobs.py) and oaths kept as quests (dungeon/quests.py)."""
import json
from datetime import datetime, timedelta

import pytest
from conftest import tell
from test_inventory import begin
from test_travel import Road, ok, reply

from dungeon import factions, inventory, jobs, quests

NOW = datetime(1290, 5, 1, 12)


@pytest.fixture
def hiring(monkeypatch):
    monkeypatch.setattr(factions, 'ACTIVE', True)
    monkeypatch.setattr(jobs, 'OFFER', 100)


def test_a_faction_holding_the_town_offers_work(client, connected, provider, app, hiring):
    begin(client)
    app.state.dice = Road(1)
    reply(provider, 'A notice on the door.')
    tell(client, 'I read the notices.', 'story-0001')
    narrator = provider.requests[-1]['system']
    assert "Work is going: the reeve's men (The Kingdom of Cyrel) wants it done within 5 days, for 6.00 cr." in narrator
    quest = next(item for item in ok(client.get('/api/story/journal'))['quests'] if item['kind'] == 'job')
    assert quest['title'] == 'A deserter in the woods' and quest['left'].startswith('about 5 days')
    # The truth reaches the narrator only; the job leaves its ties for the story director.
    assert 'sold the company\'s winter boots' in narrator and 'sold the company' not in quest['hook']
    with app.state.database.connect() as connection:
        row = connection.execute("SELECT ties, reward, faction_id FROM story_quests WHERE kind='job'").fetchone()
    assert json.loads(row['ties'])[0] == {'kind': 'npc', 'ref': 'the deserter'} and row['reward'] == 600
    # One job open at a time for each faction: the next day's offer is another faction's.
    with app.state.database.connect(write=True) as connection:
        offered = jobs.offer(connection, 'vallarith', 'kingswood', 'kingswood', 150, {'symbol': 'cr.'}, NOW, Road(1))
    assert 'The Cyrel Timber Guild' in offered[0]


def test_a_job_done_pays_and_earns_standing_and_one_failed_costs_it(app):
    with app.state.database.connect(write=True) as connection:
        inventory.set_purse(connection, 100)
        done = quests.create(connection, 'job', 'kingswood', 'Collect', 'hook', 'truth', 'missed', None,
                             faction_id='cyrel-timber-guild', reward=450, standing=2)
        quests.end(connection, done, 'done', 'Collected.')
        assert inventory.purse(connection) == 550 and factions.standing(connection, 'cyrel-timber-guild') == 2
        failed = quests.create(connection, 'job', 'kingswood', 'Saws', 'hook', 'truth', 'missed', None,
                               faction_id='cyrel-timber-guild', reward=450, standing=2)
        quests.end(connection, failed, 'failed', 'Named the wrong man.')
        assert factions.standing(connection, 'cyrel-timber-guild') == 1 and inventory.purse(connection) == 550
        # One left to lapse costs only what happens.
        quests.create(connection, 'job', 'kingswood', 'Lapsed', 'hook', 'truth', 'Nobody came.',
                      (NOW + timedelta(days=1)).isoformat(), faction_id='cyrel-timber-guild')
        quests.check(connection, NOW + timedelta(days=2), '2026-10-22')
        assert factions.standing(connection, 'cyrel-timber-guild') == 1


def test_an_oath_is_kept_as_a_quest_and_breaking_it_costs_trust(app):
    answer = ('{"facts": [], "oaths": [{"to": "Corin Ashby", "text": "Pay back the ten crowns by market day.", '
              '"days": 3}, {"to": "nobody", "text": ""}]}')
    sworn = quests.oaths(answer)
    assert sworn == [{'to': 'Corin Ashby', 'text': 'Pay back the ten crowns by market day.', 'days': 3}]
    with app.state.database.connect(write=True) as connection:
        connection.execute("INSERT INTO story_people (key, city_id, name, first_met_at, last_met_at, last_day) VALUES "
                           "('corin', 'kingswood', 'Corin Ashby', 'x', 'x', 'x')")
        quest_id = quests.swear(connection, 'kingswood', sworn[0], NOW)
        quest = next(item for item in quests.rows(connection) if item['id'] == quest_id)
        assert quest['kind'] == 'oath' and quest['title'] == 'An oath to Corin Ashby' and quest['known']
        assert quest['ties'] == [{'kind': 'npc', 'ref': 'Corin Ashby'}]
        quests.check(connection, NOW + timedelta(days=4), '2026-10-22')
        row = connection.execute("SELECT trust, respect FROM story_people WHERE key='corin'").fetchone()
        assert (row['trust'], row['respect']) == (-2, -1)
        assert quests.rows(connection, 'missed')[0]['outcome'] == 'The oath to Corin Ashby was broken. Corin Ashby ' \
                                                                  'remembers.'
