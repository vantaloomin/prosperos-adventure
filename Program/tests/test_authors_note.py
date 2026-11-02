"""Author's note: one note per chat, sent last before the user's words with every reply while it is on, and never part
of the story (dungeon/authors_note.py)."""


NOTE = "Mira's exhausted from the commute. Keep it short tonight."


def ok(response):
    assert response.status_code == 200, response.text
    return response.json()


def put(client, chat, text, enabled=True):
    return ok(client.put(f'/api/authors-notes/{chat}', json={'text': text, 'enabled': enabled}))


def current(client) -> str:
    return ok(client.get('/api/companion'))['companion']['id']
