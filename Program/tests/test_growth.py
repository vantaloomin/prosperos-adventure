"""Progression (dungeon/growth.py): growth by use and milestones, and the dark tracks."""
from conftest import tell
from test_feelings import reply as chunks
from test_feelings import say
from test_inventory import begin
from test_travel import Road, ok, reply

from dungeon import growth, quests, record, sheet, tiers
from dungeon.life import cards

WON = {'actor': sheet.PERSONA, 'stat': 'Vitality', 'band': 'success'}


def test_a_roll_that_mattered_marks_its_stat_once_a_line(app):
    with app.state.database.connect(write=True) as connection:
        growth.mark(connection, [WON, {'actor': sheet.PERSONA, 'stat': 'Mind', 'band': 'failure'},
                                 {'actor': sheet.PERSONA, 'stat': 'Luck', 'band': 'failure', 'threat': 'A fall.'}], 'm1')
        growth.mark(connection, [WON], 'm1')
        assert growth.marked(connection) == ['Luck', 'Vitality']
        growth.mark(connection, [WON], 'm2')
        uses = connection.execute("SELECT uses FROM story_marks WHERE stat='Vitality'").fetchone()['uses']
    assert uses == 2


def test_a_nights_rest_turns_use_into_growth(client, connected, provider, app):
    begin(client)
    with app.state.database.connect(write=True) as connection:
        sheet.set_stats(connection, {'Vitality': 10, 'Mind': 10}, 'x')
        growth.mark(connection, [WON, WON | {'stat': 'Mind'}], 'm0')
    # Mind's growth roll, not over 30, fails; Vitality's passes.
    app.state.dice = Road(20, 31)
    reply(provider, 'Morning.')
    tell(client, 'I go to bed.', 'story-0001')
    narrator = provider.requests[-1]['system']
    assert 'Vitality grows from 10 to 11' in narrator and 'Mind grows' not in narrator
    with app.state.database.connect() as connection:
        assert sheet.stats(connection)['Vitality'] == 11 and growth.marked(connection) == []
    assert ok(client.get('/api/story/sheet'))['growth'] == {'marked': [], 'dark': [], 'bonds': {'word': 'no one to call on', 'bonds': []}}


def test_a_milestone_boosts_the_stat_used_most(app):
    with app.state.database.connect(write=True) as connection:
        tiers.begin(connection, 'vallarith')
        growth.mark(connection, [WON], 'm1')
        growth.mark(connection, [WON], 'm2')
        growth.mark(connection, [WON | {'stat': 'Mind'}], 'm2')
        before = sheet.stats(connection)['Vitality']
        quest = quests.create(connection, 'authored', 'kingswood', 'The Heartwood contract', 'hook', 'truth', '', None)
        lines = quests.end(connection, quest, 'done', 'Done.', 'stamp')
        assert lines == [f"A milestone (The Heartwood contract): the character's Vitality grows from {before} to "
                         f'{before + 2}.']
        assert any(row['text'] == lines[0] for row in record.entries(connection))
        # Rising a tier is one too; uses start again from nothing.
        growth.mark(connection, [WON | {'stat': 'Mind'}], 'm3')
        job = quests.create(connection, 'job', 'kingswood', 'Big work', 'hook', 'truth', '', None, tier=3)
        lines = quests.end(connection, job, 'done', 'Done.', 'stamp')
        assert lines[0].startswith("The character's renown rises: Regional")
        assert lines[1].startswith("A milestone (a rise in standing): the character's Mind grows")


def test_a_dark_track_grants_power_changes_the_character_and_can_take_them(client, connected, provider, app):
    begin(client)
    with app.state.database.connect(write=True) as connection:
        essence = sheet.stats(connection)['Essence']
        assert growth.darken(connection, 'corruption', 2, cards.PRESETS['unflinching'], 'x', Road()) == []
        lines = growth.darken(connection, 'corruption', 1, cards.PRESETS['restrained'], 'x', Road())
        assert lines[0] == f"Corruption gives as it takes: the character's Essence grows from {essence} to {essence + 2}."
        assert lines[1] == 'A lasting change (corruption): Their shadow lags a moment behind them, and dogs will not ' \
                           'come near.'
        assert lines[2] == "The character's corruption: now tainted."
        # Restrained allows no change past the first level of horror.
        assert growth.darken(connection, 'corruption', 3, cards.PRESETS['restrained'], 'x', Road())[1] == \
            'A lasting change (corruption): They hear a patient voice when they are alone, and it is often right.'
        assert 'Corruption: marked. Lasting: Their shadow lags' in growth.prompt_text(connection)
        growth.darken(connection, 'corruption', 9, cards.PRESETS['unflinching'], 'x', Road())
        assert growth.lost(connection) == 'Corruption'
    assert ok(client.get('/api/story/sheet'))['growth']['dark'][0]['word'] == 'lost'
    response = client.post('/api/story/messages', json={'text': 'I go on.', 'client_id': 'story-0009'})
    assert response.status_code == 409 and 'lost to Corruption' in response.json()['detail']


def test_the_continuity_model_says_what_feeds_a_dark_track(client, connected, provider, app):
    begin(client)
    profiles = ok(client.get('/api/models'))['profiles']
    ok(client.put('/api/models/routes', json={'job': 'continuity', 'profile_id': profiles[0]['id']}))
    provider.replies = [chunks('You take the dust.'), chunks('{"facts": [], "dark": ["addiction", "nonsense"]}')]
    say(client, 'I take the dust he offers.', 'story-0001')
    assert 'add "dark": ["one of: corruption, addiction, infamy"]' in str(provider.requests[-1])
    with app.state.database.connect() as connection:
        assert growth.dark(connection)['addiction']['points'] == 1
    assert growth.darkened('{"dark": ["infamy", "infamy"]}') == ['infamy'] and growth.darkened('no') == []
