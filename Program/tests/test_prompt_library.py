from adventure import prompt_library


def test_every_prompt_is_listed_with_its_default_and_placeholder_help(client):
    listed = {item['name']: item for item in client.get('/api/prompts').json()}
    assert set(listed) == set(prompt_library.PROMPTS) == {
        'story-narrator', 'narrator-craft', 'round-writer', 'authors-note', 'character-mind', 'character-declare',
        'character-react', 'character-ask', 'character-answer', 'character-offpage', 'character-invite',
        'character-turning', 'character-genre-dark-romantasy', 'character-genre-adventure',
        'character-genre-graphic-violence',
        'character-layout', 'genre-dark-romantasy', 'genre-adventure', 'genre-graphic-violence'}
    assert {item['group'] for item in listed.values()} == {'Story', 'Characters', 'Genres'}
    # The mind names nobody now, so every character shares it; the name is the layout's {{CHARACTER}} slot.
    assert listed['character-mind']['placeholders'] == []
    layout = listed['character-layout']
    assert layout['placeholders'] == [] and [slot['tier'] for slot in layout['slots']] == sorted(
        slot['tier'] for slot in layout['slots'])
    assert {'SHEET', 'LORE', 'MEM', 'FEELINGS', 'MOMENT'} <= {slot['name'] for slot in layout['slots']}
    narrator = listed['story-narrator']
    assert narrator['group'] == 'Story' and not narrator['customized'] and not narrator['outdated']
    assert narrator['text'] == narrator['default'] and 'narrator' in narrator['default']
    for item in listed.values():
        assert set(item['placeholder_help']) == set(item['placeholders'])
        assert all(item['placeholder_help'].values()), item['name']


def test_placeholder_typos_are_refused_before_they_reach_a_reply(client):
    extra = client.put('/api/prompts/story-narrator', json={'text': 'Narrate for {{name}}.'})
    assert extra.status_code == 422 and 'has none' in extra.json()['detail']
    assert client.put('/api/prompts/no-such-prompt', json={'text': 'x'}).status_code == 404
    assert not any(item['customized'] for item in client.get('/api/prompts').json())


def test_saving_the_default_wording_is_the_same_as_resetting(client):
    default = prompt_library.PROMPTS['narrator-craft'].default()
    assert not client.put('/api/prompts/narrator-craft', json={'text': default}).json()['customized']


def test_the_story_uses_the_users_wording(client):
    client.put('/api/prompts/authors-note', json={'text': 'A note from the player follows.'})
    database = client.app.state.database
    with database.connect() as connection:
        assert prompt_library.text(connection, 'authors-note') == 'A note from the player follows.'
        assert prompt_library.text(connection, 'narrator-craft') == prompt_library.PROMPTS['narrator-craft'].default()
    assert client.delete('/api/prompts/authors-note').json()['customized'] is False


def test_every_agent_purpose_has_its_own_editable_prompt():
    from adventure.rounds import agents
    assert {f'character-{purpose}' for purpose in agents.PURPOSES} <= set(prompt_library.PROMPTS)


def test_the_round_writer_and_the_characters_use_the_users_wording(client):
    from adventure.rounds import writer
    assert prompt_library.PROMPTS['round-writer'].default() == writer.ROUND
    refused = client.put('/api/prompts/character-mind', json={'text': 'You are {{character}}.'})
    assert refused.status_code == 422 and '{{CHARACTER}}' in refused.json()['detail']
    saved = client.put('/api/prompts/character-mind', json={'text': 'You are a character, and nobody else.'})
    assert saved.json()['customized']
    with client.app.state.database.connect() as connection:
        assert prompt_library.text(connection, 'character-mind') == 'You are a character, and nobody else.'
    client.delete('/api/prompts/character-mind')


def test_a_layout_that_puts_a_faster_changing_slot_first_is_refused(client):
    from adventure.rounds import agents
    early = agents.LAYOUT.replace('{{MEM}}', '').replace('{{SHEET}}', '{{MEM}}\n{{SHEET}}')
    refused = client.put('/api/prompts/character-layout', json={'text': early})
    assert refused.status_code == 422 and refused.json()['code'] == 'prompt_layout'
    assert 'Put {{SHEET}} before {{MEM}}' in refused.json()['detail']
    unknown = client.put('/api/prompts/character-layout', json={'text': agents.LAYOUT + '\n\n{{SIGNS}}'})
    assert unknown.status_code == 422 and 'does not fill {{SIGNS}}' in unknown.json()['detail']
    twice = client.put('/api/prompts/character-layout', json={'text': agents.LAYOUT + '\n\n{{CUE}}'})
    assert twice.status_code == 422 and 'once' in twice.json()['detail']
    # Leaving slots out is allowed: the app puts them back at the end of their tier.
    saved = client.put('/api/prompts/character-layout', json={'text': '{{SHEET}}\n\nNow decide.\n\n{{MOMENT}}'})
    assert saved.status_code == 200 and saved.json()['customized']
    client.delete('/api/prompts/character-layout')


def test_every_default_layout_keeps_the_tier_order():
    from adventure import prompt_layout
    for prompt in prompt_library.PROMPTS.values():
        if prompt.layout:
            assert prompt_layout.problems(prompt.default(), prompt.layout(), prompt.reader) is None, prompt.name
            assert set(prompt_layout.slots_in(prompt.default())) == set(prompt.layout()), prompt.name
