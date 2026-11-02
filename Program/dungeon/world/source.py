"""The shipped city data as the life simulation's world source (see dungeon/life/world.py)."""
from datetime import date, timedelta
from typing import Sequence

from dungeon.almanac import days as almanac_days
from dungeon.life.world import Place
from dungeon.world import catalog, changes, custom
from dungeon.world.generators import SEASONS, conditions, unit

# The composer's place kinds, answered from this data's place kinds (and tags, for waterfronts and books).
KINDS = {
    'park': ('park', 'garden', 'trail'), 'cafe': ('cafe',), 'restaurant': ('restaurant', 'tavern', 'inn'),
    'bar': ('bar', 'nightlife', 'tavern'), 'museum': ('museum',), 'attraction': ('attraction', 'landmark'),
    'market': ('market',), 'grocery': ('market',), 'library': ('library',), 'gym': ('fitness',),
    'beach': ('beach',), 'venue': ('venue', 'stadium'), 'shop': ('shopping',), 'vet': ('vet',),
}
TAGGED = {'waterfront': {'waterfront', 'harbour', 'harbor', 'docks', 'beach'}, 'bookstore': {'books', 'bookshop'}}
# A tag only makes a place one of these kinds when the place is outdoors: a waterfront distillery bar is no
# place for a walk along the water.
TAGGED_OUTDOORS = {'waterfront': {'park', 'garden', 'trail', 'beach', 'landmark', 'attraction', 'market', 'docks'}}
# Everyday stops a person makes close to home; museums, venues and beaches stay city-wide.
LOCAL = {'cafe', 'restaurant', 'bar', 'market', 'grocery', 'library', 'gym', 'park', 'vet'}
# How far "near home" reaches; with fewer than ENOUGH places that close, the nearest ENOUGH + 1 instead.
NEAR_KM, ENOUGH = 3.0, 2


class CatalogWorld:
    """Built-in cities, plus the user's own when given the workspace database."""
    name = 'catalog'

    def __init__(self, database=None):
        self.database = database

    def find(self, city: str, day: date | None = None) -> dict | None:
        """The city's data; with `day`, as it stands that day after its changes (see dungeon/world/changes.py)."""
        if not self.database:
            data = changes.resolve(city, {})
            return changes.apply(data, changes.known(data, day), day) if data and day else data
        with self.database.connect() as connection:
            data = changes.resolve(city, custom.all_cities(connection))
            saved = changes.stored(connection, data['id']) if data and day else None
        return changes.apply(data, changes.known(data, day, saved), day) if saved else data

    def changes(self, city: str, day: date) -> list[dict]:
        """Changes to the city people have heard of by `day`, oldest first."""
        if not self.database:
            data = changes.resolve(city, {})
            return changes.known(data, day) if data else []
        with self.database.connect() as connection:
            data = changes.resolve(city, custom.all_cities(connection))
            return changes.known(data, day, changes.stored(connection, data['id'])) if data else []

    def weather(self, city: str, day: date) -> dict | None:
        """Typical weather for the date from the city's monthly climate, the same for everyone there."""
        data = self.find(city)
        return conditions(data, day) if data else None

    def happenings(self, city: str, day: date) -> list[dict]:
        """The city's annual events held on this date. The data gives only their months, so each year
        one Saturday in one of those months is chosen from a seed of the city, event and year. Whole
        seasons (a team's season, "The London Season") are not one-day outings and are left out. Modern US
        cities add the day's parties from the almanac (dungeon/almanac/days.py)."""
        data = self.find(city)
        if not data:
            return []
        hoods = {hood['id']: hood['name'] for hood in data['neighborhoods']}
        return [{'id': item['id'], 'name': item['name'], 'kind': 'event', 'city': data['name'],
                 'neighborhood': hoods.get(item['neighborhood'], ''), 'summary': item['summary']}
                for item in data['annual_events'] if day.month in item['months'] and not seasonal(item)
                and festival_day(data['id'], item, day.year) == day] + almanac_days.gatherings(data, day)

    def places(self, city: str, kinds: Sequence[str], *, day_part: str | None = None,
               day: date | None = None, near: str | None = None) -> list[Place]:
        """Places of these kinds, open at `day_part` (morning, afternoon, evening, late) and in season on `day`.

        `near` is the person's neighborhood (an id, or free text such as their location "Fells Point,
        Baltimore"). Everyday kinds (cafes, gyms, groceries and so on) then keep to places within a short
        trip of it, or the nearest few when fewer than two are that close."""
        data = self.find(city, day)
        if not data:
            return []
        season = SEASONS[day.month] if day else None
        hoods = {hood['id']: hood['name'] for hood in data['neighborhoods']}
        close = nearby(data, near)
        result, seen = [], set()
        for kind in kinds:
            matches = [item for item in data['places'] if (item['kind'] in KINDS.get(kind, ())
                       or set(item['tags']) & TAGGED.get(kind, set())
                       and item['kind'] in TAGGED_OUTDOORS.get(kind, {item['kind']}))
                       and (day_part is None or day_part in item['day_parts'])
                       and (season is None or not item['seasons'] or season in item['seasons'])]
            if kind == 'college':
                matches = data['colleges']
            if close and kind in LOCAL:
                matches = sorted(matches, key=lambda item: close[item['neighborhood']])
                local = [item for item in matches if close[item['neighborhood']] <= NEAR_KM]
                matches = local if len(local) >= ENOUGH else matches[:ENOUGH + 1]
            for item in matches:
                if item['id'] not in seen:
                    seen.add(item['id'])
                    result.append(Place(item['id'], item['name'], kind, data['name'], hoods[item['neighborhood']],
                                        tuple(item.get('tags', ())), tuple(item.get('spots', ()))))
        return result


def nearby(data: dict, near: str | None) -> dict[str, float]:
    """Each neighborhood's distance in km from `near`, or {} when it names no neighborhood of this city."""
    if not near:
        return {}
    hoods = {hood['id']: hood for hood in data['neighborhoods']}
    home = hoods.get(near) or next((hood for hood in data['neighborhoods'] if hood['name'].lower() == near.lower()), None)
    if home is None:
        match = catalog.resolve(near, {data['id']: data})
        home = hoods.get(match['neighborhood']) if match and match['city'] == data['id'] and match['neighborhood'] else None
    if home is None:
        return {}
    return {hood['id']: catalog.distance_km(home, hood) for hood in data['neighborhoods']}


def festival_day(city_id: str, event: dict, year: int) -> date:
    """The one Saturday this year's edition of an annual event is held on, stable for the city and year."""
    months = event['months']
    month = months[int(unit(city_id, event['id'], year, 'month') * len(months))]
    first = date(year, month, 1)
    saturday = first + timedelta(days=(5 - first.weekday()) % 7)
    saturdays = [saturday + timedelta(weeks=week) for week in range(5)
                 if (saturday + timedelta(weeks=week)).month == month]
    return saturdays[int(unit(city_id, event['id'], year, 'week') * len(saturdays))]


def seasonal(event: dict) -> bool:
    return 'season' in event['name'].lower()
