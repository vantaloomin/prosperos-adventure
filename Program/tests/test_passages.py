"""Flagged passages and Rewrite (dungeon/passages.py): what the checks leave is flagged, and any passage can be
rewritten in new words with the same dice and facts, and switched back."""
from conftest import tell
from test_pace import Slow, ok, reply, route

from dungeon import passages, record


def narration(client):
    return ok(client.get('/api/story'))['messages'][-1]


def dead(app, subject, truth='both'):
    with app.state.database.connect(write=True) as connection:
        record.add(connection, 'death', subject, f'{subject} drowned off the pier.', app.state.database.now(),
                   truth=truth)


def test_what_the_checks_leave_is_flagged_with_why_and_a_hidden_death_stays_hidden(client, connected, provider, app):
    app.state.pace_clock = Slow()
    dead(app, 'Old Tom')
    dead(app, 'Gus', 'world')
    provider.replies = [reply('Old Tom waves from the door.\n\nThe fire is low.\n\nGus pours you a drink. '
                              'And somehow that was enough.')]
    tell(client, 'I sit down at the bar.', 'story-0001')
    flags = narration(client)['flags']
    assert [flag['passage'] for flag in flags] == ['Old Tom waves from the door.',
                                                   'Gus pours you a drink. And somehow that was enough.']
    assert flags[0]['why'] == ['The record says Old Tom is dead.']
    assert passages.HIDDEN in flags[1]['why'] and not any('Gus' in why for why in flags[1]['why'])
    assert any('somehow that was enough' in why for why in flags[1]['why'])
    assert set(flags[0]) == {'passage', 'why'}


def test_a_clean_turn_has_no_flags(client, connected, provider):
    provider.replies = [reply('The barman nods.')]
    tell(client, 'I sit down at the bar.', 'story-0001')
    assert narration(client)['flags'] == [] and narration(client)['previous'] is False


def test_a_passage_is_rewritten_with_the_same_dice_and_switched_back(client, connected, provider, app):
    ok(client.put('/api/settings', json={'show_odds': True}))
    app.state.pace_clock = Slow()
    dead(app, 'Old Tom')
    provider.replies = [reply('Old Tom waves from the door.\n\nThe fire is low and the room is quiet.')]
    tell(client, 'I punch the barman.', 'story-0001')
    rolls = ok(client.get('/api/story'))['messages'][-2]['rolls']
    told = narration(client)
    provider.replies = [reply('Old Tom\'s chair by the door sits empty.')]
    after = ok(client.post(f"/api/story/messages/{told['id']}/rewrite",
                           json={'passage': 'Old Tom waves from\nthe door.', 'note': 'he is dead'}))
    asked = provider.requests[-1]
    assert passages.SYSTEM in asked['system'] and 'Old Tom drowned' in asked['system']
    assert 'The player asks: he is dead' in asked['messages'][0]['content']
    assert 'The record says Old Tom is dead.' in asked['messages'][0]['content']
    line = after['messages'][-1]
    assert line['text'] == "Old Tom's chair by the door sits empty.\n\nThe fire is low and the room is quiet."
    assert line['flags'] == [] and line['previous'] is True and after['messages'][-2]['rolls'] == rolls
    # Switching goes back to the first wording, with its flags, and again to the rewrite.
    back = ok(client.post(f"/api/story/messages/{told['id']}/switch"))['messages'][-1]
    assert back['text'] == told['text'] and back['flags'] == told['flags']
    again = ok(client.post(f"/api/story/messages/{told['id']}/switch"))['messages'][-1]
    assert again['text'] == line['text']


def test_a_rewrite_takes_the_facts_again_and_refuses_what_is_not_there(client, connected, provider, app):
    route(client, 'continuity')
    provider.replies = [reply('The bouncer breaks your nose.\n\nThe room goes quiet.'),
                        reply('{"facts": [{"kind": "wound", "subject": "you", "text": "Your nose is broken."}]}')]
    tell(client, 'I shove the bouncer.', 'story-0001')
    told = narration(client)
    missing = client.post(f"/api/story/messages/{told['id']}/rewrite", json={'passage': 'Nothing like this'})
    assert missing.status_code == 422
    provider.replies = [reply('The bouncer flattens your nose.'),
                        reply('{"facts": [{"kind": "wound", "subject": "you", "text": "Your nose is flattened."}]}')]
    ok(client.post(f"/api/story/messages/{told['id']}/rewrite", json={'passage': 'The bouncer breaks your nose.'}))
    with app.state.database.connect() as connection:
        facts = [entry['text'] for entry in record.entries(connection)]
    assert facts == ['Your nose is flattened.']
    # Too different a rewrite is refused and the passage stays.
    provider.replies = [reply('No.')]
    refused = client.post(f"/api/story/messages/{told['id']}/rewrite", json={'passage': 'The room goes quiet.'})
    assert refused.status_code == 502 and 'The room goes quiet.' in narration(client)['text']


def test_a_part_shared_with_another_branch_is_not_rewritten(client, connected, provider):
    provider.replies = [reply('The barman nods.'), reply('The barman frowns.')]
    tell(client, 'I sit down at the bar.', 'story-0001')
    first = narration(client)
    tell(client, 'I order a drink.', 'story-0002')
    line = ok(client.get('/api/story'))['messages'][-2]
    ok(client.post('/api/story/back', json={'message_id': line['id']}))
    shared = client.post(f"/api/story/messages/{first['id']}/rewrite", json={'passage': 'The barman nods.'})
    assert shared.status_code == 409
