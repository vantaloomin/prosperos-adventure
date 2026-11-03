from adventure import prompt_library


def test_every_prompt_is_listed_with_its_default_and_placeholder_help(client):
    listed = {item['name']: item for item in client.get('/api/prompts').json()}
    assert set(listed) == set(prompt_library.PROMPTS) == {
        'story-narrator', 'narrator-craft', 'round-writer', 'authors-note', 'character-mind', 'character-declare',
        'character-react', 'character-ask', 'character-answer', 'character-offpage', 'character-turning'}
    assert {item['group'] for item in listed.values()} == {'Story', 'Characters'}
    assert listed['character-mind']['placeholders'] == ['character']
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
    refused = client.put('/api/prompts/character-mind', json={'text': 'You are a character.'})
    assert refused.status_code == 422 and '{{character}}' in refused.json()['detail']
    saved = client.put('/api/prompts/character-mind', json={'text': 'You are {{character}}, and nobody else.'})
    assert saved.json()['customized']
    with client.app.state.database.connect() as connection:
        assert prompt_library.text(connection, 'character-mind', character='Hesk') == 'You are Hesk, and nobody else.'
    client.delete('/api/prompts/character-mind')
