"""Ordinary names the companion can give someone new in conversation (a new coworker, a neighbor), so the
chat model picks from the world data instead of inventing a name. One short context section."""
from dungeon.world import changes, custom, generators, naming

# Ages spread across adulthood, so a name fits whoever the companion mentions.
AGES = (24, 29, 34, 41, 48, 57, 66)
SUFFIXES = {'jr', 'sr', 'ii', 'iii', 'iv'}


def city_for(connection, definition: dict) -> dict:
    for text in (definition.get('home_city'), definition.get('location')):
        if text and (data := changes.resolve(text, custom.all_cities(connection))):
            return data
    return naming.DEFAULT_CITY


def surname(full: str) -> str:
    """The last word of a full name ("Freeman" for Mya Freeman), or '' for a single name."""
    words = [word for word in full.split() if word.casefold().rstrip('.') not in SUFFIXES]
    return words[-1] if len(words) > 1 else ''


def context_line(connection, version: dict, timeline_id: str) -> tuple[str, str]:
    data = city_for(connection, version['definition'])
    taken = {version['definition'].get('name', '')}
    names = [generators.name(data, seed=f'newcomer:{timeline_id}:{index}', age=age,
                             avoid=[surname(version['definition'].get('name', ''))])
             for index, age in enumerate(AGES)]
    listed = [f"{item['full']} (about {age})" for item, age in zip(names, AGES) if item['full'] not in taken]
    return 'newcomers', '- ' + ', '.join(listed)
