from dungeon import prompt_library


def test_every_prompt_is_listed_with_its_default_and_placeholder_help(client):
    listed = {item['name']: item for item in client.get('/api/prompts').json()}
    assert set(listed) == set(prompt_library.PROMPTS) == {'story-narrator', 'narrator-craft', 'authors-note'}
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
