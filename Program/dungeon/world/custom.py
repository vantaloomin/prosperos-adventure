"""The user's own cities (PRD W5), stored in the workspace so backups and restores carry them.

A user city is validated exactly like a built-in one, so every generator works on it. Ids are
shared with the built-in cities and cannot shadow them.
"""
import logging

from pydantic import ValidationError

from dungeon import lore
from dungeon.database import decode, encode, optional
from dungeon.errors import DomainError, require
from dungeon.world import catalog, mend

TEMPLATE_SOURCE = 'user'
LOG = logging.getLogger(__name__)
_reported: set[tuple[str, str]] = set()


def _invalid(error: Exception) -> DomainError:
    if isinstance(error, ValidationError):
        details = '; '.join(f"{'.'.join(map(str, issue['loc'])) or 'city'}: {issue['msg']}"
                            for issue in error.errors()[:8])
    else:
        details = str(error)
    return DomainError(f'This city is not valid. {details}', 422, 'invalid_city')


def check(definition: dict) -> dict:
    """The prepared city, small mistakes mended, or a DomainError listing what is still wrong."""
    try:
        return catalog.prepare(definition, mend=True)
    except (ValidationError, ValueError) as error:
        failure = _invalid(error)
        notes = mend.mend(definition)[1] if isinstance(definition, dict) else []
        if notes:
            failure.message += ' Mended on the way: ' + ' '.join(notes[:8])
        raise failure from None


def _view(row) -> dict:
    data = catalog.prepare(decode(row['definition']), mend=True)
    return data | {'builtin': False, 'origin': 'user', 'revision': row['revision'], 'created_at': row['created_at'],
                   'updated_at': row['updated_at']}


def _load(connection) -> tuple[dict[str, dict], list[dict]]:
    """The user's cities that still validate, and the ones that no longer do (an older app's rules, a hand edit)."""
    cities, broken = {}, []
    for row in connection.execute('SELECT * FROM world_cities ORDER BY id').fetchall():
        try:
            cities[row['id']] = _view(row)
        except Exception as error:  # one city that no longer loads must not empty every list
            if not isinstance(error, (ValidationError, ValueError, KeyError, TypeError)):
                LOG.exception('Your city %r crashed while loading', row['id'])
            try:
                definition = decode(row['definition'])
            except ValueError:
                definition = None
            name = definition.get('name') if isinstance(definition, dict) else None
            broken.append({'id': row['id'], 'name': name if isinstance(name, str) and name else row['id'],
                           'error': _invalid(error).message, 'definition': definition})
    # A city the app now ships, or a pack now holds, wins over the user's own copy of it (a Los Angeles the user
    # imported before it became built-in), so no list shows it twice. The saved copy stays, and can be deleted.
    shipped = catalog.cities()
    return {key: value for key, value in cities.items() if key not in shipped}, broken


def all_cities(connection) -> dict[str, dict]:
    """The user's cities. One that no longer validates is left out, so it cannot empty every city list."""
    cities, broken = _load(connection)
    for item in broken:
        if (item['id'], item['error']) not in _reported:
            _reported.add((item['id'], item['error']))
            LOG.warning('Your city %r no longer loads and was skipped: %s', item['id'], item['error'])
    return cities


def broken(database) -> list[dict]:
    """The user's cities that no longer load, with their saved definition so they can be fixed or deleted."""
    with database.connect() as connection:
        return _load(connection)[1]


def read(database) -> dict[str, dict]:
    with database.connect() as connection:
        return all_cities(connection)


def _definition(data: dict) -> dict:
    return {key: value for key, value in data.items()
            if key not in {'data_version', 'builtin', 'origin', 'pack_file', 'revision', 'created_at', 'updated_at',
                           'import_notes'}}


def _notes(data: dict) -> dict:
    """What mending changed on the way in; the saved definition is already the mended one."""
    return {'import_notes': data['import_notes']} if data.get('import_notes') else {}


def create(database, definition: dict, also=None) -> dict:
    """Save a new city. `also(connection, timestamp)` writes what comes with it (a world map's lore) in the same
    transaction, so the two arrive together or not at all."""
    data = check(definition)
    require(data['id'] not in catalog.cities(), f'{data["id"]!r} is a built-in or pack city. Choose another id.',
            409)
    with database.connect(write=True) as connection:
        exists = optional(connection, 'SELECT id FROM world_cities WHERE id=?', (data['id'],))
        require(exists is None, f'You already have a city with id {data["id"]!r}.', 409)
        now = database.now()
        connection.execute('INSERT INTO world_cities (id, definition, created_at, updated_at) VALUES (?, ?, ?, ?)',
                            (data['id'], encode(_definition(data)), now, now))
        if also:
            also(connection, now)
        return all_cities(connection)[data['id']] | _notes(data)


def _not_builtin(city_id: str) -> None:
    require(city_id not in catalog.cities(), 'Built-in and pack cities cannot be changed here. Copy one to make it '
            'yours.', 409)


def update(database, city_id: str, definition: dict, expected_revision: int) -> dict:
    _not_builtin(city_id)
    data = check(definition)
    require(data['id'] == city_id, 'A city keeps its id. Copy it to use a new one.', 422)
    with database.connect(write=True) as connection:
        row = optional(connection, 'SELECT * FROM world_cities WHERE id=?', (city_id,))
        if row is None:
            raise DomainError(_missing(city_id), 404, 'unknown_city')
        require(row['revision'] == expected_revision, 'This city changed since you opened it. Reload it first.', 409)
        connection.execute('UPDATE world_cities SET definition=?, revision=revision+1, updated_at=? WHERE id=?',
                           (encode(_definition(data)), database.now(), city_id))
        return all_cities(connection)[city_id] | _notes(data)


def delete(database, city_id: str) -> None:
    with database.connect(write=True) as connection:
        if optional(connection, 'SELECT id FROM world_cities WHERE id=?', (city_id,)) is None:
            _not_builtin(city_id)
            raise DomainError(_missing(city_id), 404, 'unknown_city')
        if city_id in catalog.cities():
            # Only the user's saved copy of a city that is now built in goes; the built-in one stays.
            connection.execute('DELETE FROM world_cities WHERE id=?', (city_id,))
            return
        home = optional(connection, 'SELECT home_city_id FROM persona WHERE id=1')
        require(not home or home['home_city_id'] != city_id, 'You live in this city. Move your home first.', 409)
        row = optional(connection, 'SELECT definition FROM world_cities WHERE id=?', (city_id,))
        lore.forget_city(connection, {**_decoded(row['definition']), 'id': city_id})
        connection.execute('DELETE FROM world_cities WHERE id=?', (city_id,))


def copy(database, source_id: str, new_id: str, name: str) -> dict:
    """Start a city of one's own from any city, built-in or the user's."""
    with database.connect() as connection:
        source = catalog.city(source_id, all_cities(connection))
    return create(database, _definition(source) | {'id': new_id, 'name': name, 'aliases': []})


def template(today: str) -> dict:
    """The smallest valid city, for the interface's "start from scratch"."""
    return {
        'schema_version': 1, 'id': 'my-city', 'name': 'My city', 'setting': 'original', 'era': 'modern',
        'region': 'Region', 'country': 'Country', 'timezone': 'UTC', 'summary': 'A few words about the city.',
        'lat': 0.0, 'lon': 0.0,
        'sources': {TEMPLATE_SOURCE: {'kind': 'user', 'title': 'Written by the user', 'license': 'User content',
                                      'retrieved': today}},
        'neighborhoods': [{'id': 'old-town', 'name': 'Old Town', 'summary': 'The oldest streets in the city.',
                           'vibe': ['historic'], 'lat': 0.0, 'lon': 0.0, 'housing': ['apartment'],
                           'walkability': 'high', 'source': TEMPLATE_SOURCE}],
        'places': [{'id': 'corner-cafe', 'name': 'The corner cafe', 'kind': 'cafe', 'neighborhood': 'old-town',
                    'summary': 'A small cafe on the main square.', 'cost': '$', 'setting': 'indoor',
                    'good_for': ['solo', 'friends'], 'day_parts': ['morning', 'afternoon'],
                    'source': TEMPLATE_SOURCE}],
    }


def _decoded(text: str) -> dict:
    try:
        found = decode(text)
    except ValueError:
        return {}
    return found if isinstance(found, dict) else {}


def _missing(city_id: str) -> str:
    return f'You have no city with id {city_id!r}.'
