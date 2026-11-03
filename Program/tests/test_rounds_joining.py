"""An agent asked along answers for themselves (adventure/rounds/joining.py; docs/spec.md, code and model boundary
follow-ups: "Agents choose whether to leave the party; feelings still limit who joins")."""
from conftest import tell
from test_bonds import met
from test_inventory import begin
from test_travel import reply

from adventure import feelings, party, story, story_clock
from adventure.database import decode, one
from adventure.rounds import agents, seats, writer
from adventure.rounds.contract import Declaration, Line, Mind


class Calls(list):
    joins = False


def someone_here(app) -> dict:
    """The one person at Pell's, made an agent."""
    with app.state.database.connect(write=True) as connection:
        view = story.scene(connection, story_clock.now(connection, app.state.database.clock))
        [person] = [person for person in view['people'] if not person.get('party')]
        found = person['sheet']
        seats.set_seat(connection, found['key'], found['full'], '', mind=Mind.AGENT)
    return found


def last_draft(app) -> dict:
    with app.state.database.connect() as connection:
        return decode(one(connection, "SELECT draft FROM round_turns WHERE state='committed' ORDER BY rowid DESC "
                                      'LIMIT 1')['draft'])


def test_an_agent_asked_along_can_turn_the_character_down(client, connected, provider, app, monkeypatch):
    held = Calls()

    async def ask(turn, key, purpose='declare', cue=None):
        held.append((key, purpose, cue))
        if purpose == 'invite':
            said = Declaration(seat=key, lines=[Line('Not this road, friend.')], motive='The shop needs me.')
            return {'change': True, 'declaration': said, 'answer': {'joins': held.joins}}
        return {'change': False, 'declaration': Declaration(seat=key, intent='minds the counter'), 'answer': {}}

    async def speak(turn, key, cue):
        return Declaration(seat=key)
    monkeypatch.setattr(agents, 'ask', ask)
    monkeypatch.setattr(agents, 'speak', speak)
    begin(client)
    found = someone_here(app)
    first = found['name'] or found['full'].split(' ')[0]
    reply(provider, 'They shake their head.')
    tell(client, f'"Come with me, {first}."', 'story-0001')
    [(key, purpose, cue)] = [call for call in held if call[1] == 'invite']
    assert key == found['key'] and first in cue['line']
    [system] = [request['system'] for request in provider.requests if request['system'].startswith(writer.ROUND)]
    assert f"{found['full']} turns the character down, by their own choice" in system
    assert 'Not this road, friend.' in system
    draft = last_draft(app)
    assert draft['extra']['joining'] == {found['key']: False}
    assert any(item['kind'] == 'motive' and item['text'] == 'The shop needs me.' for item in draft['knowledge'])
    with app.state.database.connect() as connection:
        assert party.keys(connection) == set()

    # Asked again on a later line, they say yes: no Allure roll stands in their way.
    held.joins = True
    reply(provider, 'They untie their apron.')
    tell(client, f'"Come with me after all, {first}."', 'story-0002')
    with app.state.database.connect() as connection:
        assert party.keys(connection) == {found['key']}


def test_a_wary_agent_is_never_asked_and_won_t_come(client, connected, provider, app, monkeypatch):
    held = Calls()

    async def ask(turn, key, purpose='declare', cue=None):
        held.append((key, purpose, cue))
        return {'change': False, 'declaration': Declaration(seat=key, intent='minds the counter'),
                'answer': {'joins': True}}

    async def speak(turn, key, cue):
        return Declaration(seat=key)
    monkeypatch.setattr(agents, 'ask', ask)
    monkeypatch.setattr(agents, 'speak', speak)
    begin(client)
    found = someone_here(app)
    with app.state.database.connect(write=True) as connection:
        if one(connection, 'SELECT COUNT(*) AS n FROM story_people WHERE key=?', (found['key'],))['n'] == 0:
            met(connection, found['key'], found['full'])
        feelings.change(connection, found['key'], {'trust': -2})
    reply(provider, 'They look away.')
    tell(client, f"\"Come with me, {found['name'] or found['full'].split(' ')[0]}.\"", 'story-0001')
    assert not [call for call in held if call[1] == 'invite']
    [system] = [request['system'] for request in provider.requests if request['system'].startswith(writer.ROUND)][-1:]
    assert "won't come along" in system
