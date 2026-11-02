"""Range bands and named areas in a fight (dungeon/ranges.py, dungeon/combat.py)."""
from dungeon import combat, quests, ranges

NOW = '2026-10-01T12:00:00Z'


class Dice:
    """Every d100 shows `natural`; every other die rolls lowest."""

    def __init__(self, natural):
        self.natural = natural

    def randint(self, low, high):
        return self.natural if (low, high) == (1, 100) else low

    def choice(self, items):
        return items[0]


def foe(**values):
    return {'id': 'f', 'name': 'the bandit', 'vitality': 10, 'resolve': 30, 'weapon': 0, 'wound': 0,
            'zone': 'engaged', 'broken': False} | values


def begin(client):
    client.put('/api/story/scene', json={'city_id': 'kingswood', 'place_id': 'felled-oak'})
    client.delete('/api/story')
    client.post('/api/story/start', json={'premade_id': 'agna-holt'})


def roll(action, band='success'):
    return {'action': action, 'stat': 'Vitality', 'band': band}


def test_lines_that_shoot_back_off_or_name_a_place():
    assert ranges.ranged('I loose an arrow at the archer.') and not ranges.ranged('I cut at him.')
    assert ranges.backing('I fall back to the stairs.') and ranges.backing('I step back out of reach.')
    assert not ranges.backing('I hold my ground.')
    assert ranges.area('I fall back to the stairs and wait.') == 'the stairs'
    assert ranges.area('I duck behind the bar.') == 'the bar'
    assert ranges.area('I step back.') is None


def test_far_foes_close_a_band_a_round_and_archers_shoot_from_where_they_stand():
    lines = []
    walker, archer = foe(zone='far'), foe(name='the archer', zone='far', ranged=True)
    assert ranges.close(walker, lines) and walker['zone'] == 'near'
    assert ranges.close(walker, lines) and walker['zone'] == 'engaged'
    assert not ranges.close(walker, lines)
    assert not ranges.close(archer, lines) and archer['zone'] == 'far'
    assert lines == ['The bandit comes nearer.', 'The bandit closes in.']


def test_a_blow_cannot_reach_a_far_foe_but_a_shot_can_and_leaves_it_there(app, client):
    begin(client)
    with app.state.database.connect(write=True) as connection:
        state = {'round': 0, 'wants': 'kill', 'foes': [foe(zone='far', resolve=100)]}
        state, lines, _ = combat.play_round(connection, state, [roll('I charge and cut at the bandit.')], [], Dice(80))
        assert lines[0] == "The player's character closes on the bandit, still too far off to strike this round."
        assert state['foes'][0]['wound'] == 0 and state['foes'][0]['zone'] == 'engaged'

        state = {'round': 0, 'wants': 'kill', 'foes': [foe(zone='far', resolve=100)]}
        state, lines, _ = combat.play_round(connection, state, [roll('I shoot the bandit with my bow.')], [], Dice(80))
        assert lines[0].startswith("The player's character hits the bandit")
        # Hit where it stood, it still comes on.
        assert state['foes'][0]['wound'] > 0 and lines[1] == 'The bandit comes nearer.'


def test_falling_back_to_the_stairs_breaks_away_and_the_narrator_hears_where(app, client):
    begin(client)
    with app.state.database.connect(write=True) as connection:
        state = {'round': 0, 'wants': 'kill', 'foes': [foe(resolve=100)]}
        state, lines, ending = combat.play_round(connection, state, [roll('I fall back to the stairs.')], [], Dice(80))
        assert ending == '' and lines[0] == ("The player's character breaks away to the stairs: the foes must close "
                                             'again.')
        # Shaken off, the bandit loses this round's turn and stays near; the area outlasts the line.
        assert lines[1] == 'The bandit is left behind for now.' and state['area'] == 'the stairs'
        assert ranges.positions(state, combat.standing(state)) == ("The player's character is at the stairs. Ranges: "
                                                                    'the bandit: near.')
        combat.save_fight(connection, state)
        state = combat.fight(connection)
        assert state['area'] == 'the stairs'
        state, lines, _ = combat.play_round(connection, state, [roll('I wait for him.')], [], Dice(80))
        assert 'The bandit closes in.' in lines and state['area'] == 'the stairs'
        failed = {'round': 0, 'wants': 'kill', 'foes': [foe(resolve=100)]}
        _, lines, _ = combat.play_round(connection, failed, [roll('I fall back to the stairs.', 'failure')], [],
                                        Dice(80))
        assert lines[0] == "The player's character tries to back off and cannot shake them."


def test_the_heartwood_wardens_shoot_from_the_trees(app, client):
    begin(client)
    spec = next(threat['foe'] for item in quests.adventure('kingswood')['dangers'] for threat in item['threats']
                if isinstance(threat, dict) and threat['foe']['name'] == 'warden of Brynwyr')
    with app.state.database.connect(write=True) as connection:
        state = combat.begin(connection, [], [], spec, Dice(99))
        assert all(item['zone'] == 'far' and item['ranged'] for item in state['foes'])
        _, lines, _ = combat.play_round(connection, state, [], [], Dice(80))
        assert all('hits the player' in line for line in lines)


def test_bedding_down_mid_fight_is_no_feat_to_roll(app, client, connected, provider, monkeypatch):
    # E2E vows pass: "I sleep until morning" mid-fight was rolled as an action against Great.
    from conftest import tell
    from test_rulesets import reply

    from dungeon import record, referee
    begin(client)
    with app.state.database.connect(write=True) as connection:
        combat.save_fight(connection, {'round': 0, 'wants': 'drive_off', 'foes': [foe(zone='far', resolve=100)]})

    async def a_feat(*_):
        return [{'action': 'I sleep until morning', 'stat': 'Resolve', 'difficulty': 'hard'}]
    monkeypatch.setattr(referee, 'decide', a_feat)
    client.put('/api/settings', json={'show_odds': True})
    provider.respond = lambda system, messages: reply(
        '{"facts": []}' if system.startswith(record.EXTRACT) else 'No sleep.')
    tell(client, 'I sleep until morning.', 'story-0001')
    asked = [message for message in client.get('/api/story').json()['messages'] if message['role'] == 'user'][-1]
    assert asked['text'] == 'I sleep until morning.' and not asked.get('rolls')


def test_a_new_campaign_has_its_world_seed_before_anything_reads_it(app, client):
    # E2E vows pass: the first GET /api/story wrote the seed (townmap.street) while the start still held the lock.
    begin(client)
    with app.state.database.connect() as connection:
        from dungeon.database import optional
        assert optional(connection, 'SELECT seed FROM story_campaign WHERE id=1')['seed']
