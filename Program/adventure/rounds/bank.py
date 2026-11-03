"""The bank: a world's leads who don't travel with the character (the cast page's Bank row).

When a town has more leads than the table seats agents (`seats` agent cap), not all of them follow the character.
The cast page fills the party up to the cap and leaves the rest in the bank; the player can swap anyone in or out
before Begin (adventure/rounds/cast.py). A lead left in the bank is not lost: they live in their town as a background
character, a city notable (adventure/world/schema.py Notable) at their usual place, the premade's `home` (else where
the story opens). They keep shifts or visits like any notable, carry their package id as `notable` so what the package
says they know still reaches them (adventure/rounds/context.py `cast_of`), and can be asked along in the story like
anyone else in town (adventure/party.py).

The bank is written once at Begin (`keep`) and read wherever the story reads its city (adventure/story.py
`city_data`), after the city's own notables so their places in town never shift.
"""
from adventure.database import decode, encode, many


def keep(connection, city_id: str, entries: list[dict]):
    """At Begin: these leads live in town as background characters, and nobody else from an earlier start does."""
    connection.execute('DELETE FROM story_bank')
    for entry in entries:
        connection.execute('INSERT INTO story_bank (key, city_id, entry) VALUES (?, ?, ?)',
                           (entry['id'], city_id, encode(entry)))


def notables(connection, city_id: str) -> list[dict]:
    """The banked leads living in this city, as its notables."""
    return [decode(row['entry']) for row in many(connection, 'SELECT entry FROM story_bank WHERE city_id=? '
                                                             'ORDER BY rowid', (city_id,))]


def with_bank(connection, data: dict) -> dict:
    """The city with its banked leads among its notables, after its own."""
    found = notables(connection, data['id'])
    return data | {'notables': [*data.get('notables', ()), *found]} if found else data
