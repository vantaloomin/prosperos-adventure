"""The stress track (dungeon/stress.py): Resolve against trauma, conditions past thresholds, easing with rest."""
from datetime import datetime

from conftest import tell
from test_inventory import begin
from test_rest import out_in_the_badlands
from test_travel import Road, ok, reply

from dungeon import injuries, stress, travel

NOW = datetime(1290, 5, 1, 12)


def test_resolve_decides_how_much_a_trauma_costs(app):
    with app.state.database.connect(write=True) as connection:
        # 40 and the Resolve die is a failure with an upside: all of it.
        assert stress.add(connection, 'robbed', 'the bandits', NOW, Road(40)) == [
            'Being beaten, robbed and left for dead by the bandits weighs on the character (Resolve: failure upside): '
            'now shaken, 2 of 12.']
        # A success takes half; a critical success shrugs it off.
        stress.add(connection, 'robbed', 'the bandits', NOW, Road(60))
        assert stress.points(connection) == 3
        assert 'shrugs off' in stress.add(connection, 'captured', 'the wardens', NOW, Road(95))[0]
        # A critical failure takes one more, and past 4 the mind is marked.
        lines = stress.add(connection, 'captured', 'the wardens', NOW, Road(5))
        assert stress.points(connection) == 7 and lines[1].startswith('It leaves a lasting mark on the mind:')
        shown = injuries.active(connection, NOW)
        assert [entry['kind'] for entry in shown] == ['condition']
        assert 'lasting conditions of the mind' in injuries.prompt_text(connection, NOW)
        assert stress.view(connection, True) == 'strained, 7 of 12' and stress.view(connection, False) == 'strained'


def test_only_the_first_kill_weighs(app):
    with app.state.database.connect(write=True) as connection:
        assert 'The first life they have taken weighs' in stress.aftermath(connection, NOW, [('kill', 'the bandit')], Road(40))[0]
        assert stress.aftermath(connection, NOW, [('kill', 'the lookout')], Road(40)) == []
        assert stress.kills(connection) == 2 and stress.points(connection) == 2


def test_something_dreadful_in_the_night_frays_the_nerve(client, connected, provider, app, monkeypatch):
    out_in_the_badlands(client)
    monkeypatch.setattr(travel, 'pick', lambda entries, rng: next(entry for entry in entries if 'ghoul' in str(entry)))
    # A bad night (10), the ghoul, the Luck roll fails (15), and Resolve lands at a cost (50): half of two.
    app.state.dice = Road(10, 15)
    reply(provider, 'Shale moves.')
    tell(client, 'I make camp.', 'story-0001')
    assert 'Facing ward-ghoul weighs on the character' in provider.requests[-1]['system']
    assert ok(client.get('/api/story'))['fight']['stress'] == 'shaken'


def test_rest_eases_the_strain(client, connected, provider, app):
    begin(client)
    with app.state.database.connect(write=True) as connection:
        stress.save(connection, 3)
    app.state.dice = Road(1)
    reply(provider, 'Morning.')
    tell(client, 'I go to bed.', 'story-0001')
    assert 'Rest eases the strain: the character is shaken, 2 of 12.' in provider.requests[-1]['system']
    assert "is shaken (stress 2 of 12" in provider.requests[-1]['system']
