"""A 5E spell the player's line casts by name (dungeon/sheet.py spell_actions, unprepared; magic-towns pass): cast out
of a fight though the Referee saw nothing uncertain, at the slot the line asks for wherever it says it, and not at all
when the character has not prepared it. And bedding down mid-fight under Percentile is no feat either."""
from conftest import tell
from test_rulesets import reply
from test_srd52_subclasses import begin

from dungeon import combat, combat5e, combat_brp, record, referee, sheet
from dungeon.rules import srd52


def referee_says(monkeypatch, actions):
    async def decided(*_):
        return [dict(action) for action in actions]
    monkeypatch.setattr(referee, 'decide', decided)


def narrated(provider):
    """The narrator's system prompts, as the turn sent them."""
    systems = []

    def respond(system, messages):
        systems.append(system)
        return reply('{"facts": []}' if system.startswith(record.EXTRACT) else 'It is done.')
    provider.respond = respond
    return systems


def last_rolls(client):
    return [message for message in client.get('/api/story').json()['messages'] if message['role'] == 'user'][-1] \
        .get('rolls') or []


def test_a_line_names_the_spell_it_casts():
    assert srd52.cast_named('I cast Cure Wounds at 2nd level on myself')['id'] == 'cure-wounds'
    assert srd52.cast_named('I cast magic missile at him')['id'] == 'magic-missile'
    # A spell's name alone is a word, not a cast.
    assert srd52.cast_named('I sleep until morning') is None and srd52.cast_named('I light a fire') is None


def test_healing_out_of_a_fight_is_cast_though_the_referee_saw_nothing_to_roll(client, app, connected, provider,
                                                                                monkeypatch):
    begin(client, app, 'cleric', 'acolyte', 3)
    with app.state.database.connect(write=True) as connection:
        found = sheet.native(connection)
        sheet.set_native(connection, found | {'hp': found['max_hp'] - 8}, '')
    client.put('/api/settings', json={'show_odds': True})
    referee_says(monkeypatch, [])
    narrated(provider)
    tell(client, 'I cast Cure Wounds at 2nd level on myself.', 'spell-0001')
    rolls = last_rolls(client)
    assert len(rolls) == 1 and rolls[0]['skill'].startswith('Cure Wounds (2nd-level slot) (heals ')
    with app.state.database.connect() as connection:
        healed = sheet.native(connection)
    assert healed['hp'] > found['max_hp'] - 8 and healed['spells']['used'][:2] == [0, 1]


def test_the_slot_is_read_wherever_the_line_says_it(client, app, connected, provider, monkeypatch):
    begin(client, app, 'wizard', 'sage', 3)
    with app.state.database.connect(write=True) as connection:
        found = sheet.native(connection)
        sheet.set_native(connection, found | {'spells': found['spells'] | {'prepared': ['burning-hands']}}, '')
    client.put('/api/settings', json={'show_odds': True})
    # The Referee's split leaves the slot behind: "at 2nd level" came after the target.
    referee_says(monkeypatch, [{'action': 'cast Burning Hands at the nearer one', 'stat': 'Essence',
                                'difficulty': 'normal'}])
    narrated(provider)
    tell(client, 'I cast Burning Hands at the nearer one at 2nd level.', 'spell-0002')
    assert last_rolls(client)[0]['skill'] == 'Burning Hands (spell) (2nd-level slot)'
    with app.state.database.connect() as connection:
        assert sheet.native(connection)['spells']['used'][:2] == [0, 1]


def test_an_unprepared_spell_is_not_cast_and_nothing_is_rolled(client, app, connected, provider, monkeypatch):
    begin(client, app, 'wizard', 'sage', 3)
    with app.state.database.connect(write=True) as connection:
        found = sheet.native(connection)
        sheet.set_native(connection, found | {'spells': found['spells'] | {'prepared': ['burning-hands']}}, '')
    client.put('/api/settings', json={'show_odds': True})
    referee_says(monkeypatch, [{'action': 'I cast Magic Missile at the post', 'stat': 'Mind',
                                'difficulty': 'normal'}])
    systems = narrated(provider)
    tell(client, 'I cast Magic Missile at the post.', 'spell-0003')
    assert not last_rolls(client)
    assert any('The character does not have prepared Magic Missile: it is not cast' in system for system in systems)
    with app.state.database.connect() as connection:
        assert sheet.native(connection)['spells']['used'][0] == 0


def test_bedding_down_mid_fight_under_percentile_is_no_feat_either(client, app, connected, provider, monkeypatch):
    # Magic-towns pass: a sleep line mid-fight under BRP; #194 skips the Referee whatever the ruleset.
    from test_brp_magic import wizard
    wizard(client)
    with app.state.database.connect(write=True) as connection:
        thug = combat_brp.foes_from({'name': 'the thug'}, 'engaged')[0]
        combat.save_fight(connection, {'round': 0, 'wants': 'drive_off', 'foes': [thug]})
    referee_says(monkeypatch, [{'action': 'I sleep until morning', 'stat': 'Resolve', 'difficulty': 'hard'}])
    client.put('/api/settings', json={'show_odds': True})
    narrated(provider)
    tell(client, 'I lie down and sleep until morning.', 'spell-0004')
    assert not last_rolls(client)


def test_a_spell_beside_a_blow_is_cast_too(client, app, connected, provider, monkeypatch):
    # Recheck on 551a56f: "I cast Healing Word on myself and hit the thug with my mace" rolled only the mace.
    from test_combat5e import Always
    begin(client, app, 'cleric', 'acolyte', 3)
    with app.state.database.connect(write=True) as connection:
        found = sheet.native(connection)
        sheet.set_native(connection, found | {'hp': found['max_hp'] - 6}, '')
        thug = combat5e.foes_from({'name': 'the thug'}, 'engaged', Always(20))[0]
        combat.save_fight(connection, {'round': 0, 'wants': 'drive_off', 'foes': [thug]})
    client.put('/api/settings', json={'show_odds': True})
    referee_says(monkeypatch, [{'action': 'hit the thug with my mace', 'stat': 'Vitality', 'difficulty': 'normal'}])
    narrated(provider)
    tell(client, 'I cast Healing Word on myself and hit the thug with my mace.', 'spell-0005')
    skills = [roll['skill'] or '' for roll in last_rolls(client)]
    assert len(skills) == 2 and skills[1].startswith('Healing Word (heals ')
    # The heal is on the card (the thug may hit back the same round, so the hit points alone don't show it).
    with app.state.database.connect() as connection:
        assert sheet.native(connection)['spells']['used'][0] == 1
