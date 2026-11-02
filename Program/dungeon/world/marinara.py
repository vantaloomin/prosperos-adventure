"""Bring your Marinara world (Hit List #45): a Marinara Engine world map becomes one of the user's cities.

A world map (`.world-map.json` with `format` "marinara-hierarchical-map", the older `.hierarchical-map.json`, or a
bare definition whose `locations` name a `parentId`) is a tree of places only: no characters, no persona, no story.
Its top region becomes a city (a second top region folds in as more neighbourhoods, so one world stays one town);
regions one level under it become neighbourhoods; places and buildings people visit become places; buildings with
rooms inside become employers; labelled links between places become transit lines; and each location's notes become
world lore keyed by its name (dungeon/lore.py), in one lorebook named after the map. Streets fold into their
neighbourhood, homes ("Name's Apartment") and their rooms stay lore so nobody "goes out" to someone's bedroom, and
pictures and archived places are skipped. Map positions become small fictional offsets from the city's centre, so
distances between neighbourhoods are roughly right.

No model is asked and there is no review step ("The world exists outside of User"): the town just appears, and
what was folded, defaulted or skipped is listed in the city's import notes. Its format is described from Marinara's
public source (packages/shared/src/types/spatial-context.ts, World Maps 1.3.1).
"""
import math
import re
from typing import NamedTuple
from zoneinfo import available_timezones

from dungeon import lore
from dungeon.errors import DomainError, require
from dungeon.imports import lorebooks
from dungeon.world import catalog, custom, mend, naming
from dungeon.world.mend import slug
from dungeon.world.schema import PLACE_KINDS, TRANSIT_KINDS

FORMAT = 'marinara-hierarchical-map'
BOOK_FORMAT = lore.MAP_FORMAT
SOURCE = 'marinara'
REGIONS = ('region', 'settlement')
ROOMS = ('room', 'floor')
# One step on a parent's 0-100 grid, so a whole map spans about 20 km, a city's width.
STEP_KM = 0.2
TEXT = 400
LIMITS = {'neighborhoods': 200, 'places': 2000, 'employers': 500, 'transit': 100}
# "Name's Apartment": a home, kept as lore and never a public place.
POSSESSIVE = re.compile(r"^\s*[^\W\d_][\w-]*['’]s\s", re.UNICODE)
HOME_WORDS = {'apartment', 'apartments', 'flat', 'house', 'home', 'penthouse', 'bunker', 'loft', 'condo', 'studio',
              'dorm', 'mansion', 'cabin', 'villa', 'cottage', 'bedroom', 'quarters', 'residence'}
# Icons Marinara users pick, read as a kind of place the generators reason about (first match wins).
ICON_KINDS = {
    '☕': 'cafe', '🍞': 'cafe', '🥐': 'cafe', '🍰': 'cafe', '🧁': 'cafe', '🧋': 'cafe', '🍵': 'cafe', '🍩': 'cafe',
    '🍸': 'bar', '🍷': 'bar', '🍺': 'bar', '🍻': 'bar', '🥂': 'bar', '🍹': 'bar', '🪩': 'nightlife',
    '🍗': 'restaurant', '🍜': 'restaurant', '🍣': 'restaurant', '🍕': 'restaurant', '🍔': 'restaurant',
    '🍽': 'restaurant', '🥘': 'restaurant', '🍲': 'restaurant',
    '🎭': 'venue', '🎟': 'venue', '🎬': 'venue', '🎤': 'venue', '🎵': 'venue', '🎶': 'venue',
    '🌳': 'park', '🌲': 'park', '🌷': 'garden', '🌹': 'garden', '⛲': 'square', '🏖': 'beach', '🏟': 'stadium',
    '🖼': 'museum', '🏛': 'museum', '📚': 'shopping', '🛒': 'shopping', '🏪': 'shopping', '🛍': 'shopping',
    '👗': 'shopping', '🎀': 'shopping', '🏬': 'shopping', '🏋': 'fitness', '⛪': 'temple', '🛕': 'temple',
    '🏨': 'inn', '🏫': 'landmark', '🗼': 'landmark', '💻': 'shopping',
}
# Hierarchy type labels that only repeat Marinara's own kinds, so they say nothing about the place.
PLAIN_TYPES = {'building', 'place', 'room', 'floor', 'region', 'settlement', 'location'}
# Jobs an employer hires for, by the kinds of place inside it; a building with none is an office.
KIND_CAREERS = {'cafe': 'barista', 'restaurant': 'server', 'bar': 'bartender', 'nightlife': 'bartender',
                'shopping': 'retail-associate', 'market': 'retail-associate', 'venue': 'performer'}
OFFICE_CAREER = 'marketing-coordinator'
EVENING = {'bar', 'nightlife', 'venue'}
OUTDOOR = {'park', 'garden', 'square', 'beach', 'trail', 'stadium'}


def detect(value) -> bool:
    """A Marinara world map: the export wrapper, or a bare definition (the older shape) whose locations have parents."""
    if not isinstance(value, dict):
        return False
    if value.get('format') == FORMAT:
        return True
    found = definition_of(value).get('locations')
    return isinstance(found, list) and any(isinstance(item, dict) and 'parentId' in item for item in found)


def definition_of(value: dict) -> dict:
    found = value.get('definition')
    return found if isinstance(found, dict) else value


def text(value, limit: int | None = None) -> str:
    found = ' '.join(value.split()) if isinstance(value, str) else ''
    if limit and len(found) > limit:
        found = found[:limit - 1].rsplit(' ', 1)[0].rstrip(',;:') + '…'
    return found


def note_text(location: dict) -> str:
    """A location's public description and private model note, for lore."""
    parts = [location.get(key).strip() for key in ('description', 'modelMemory') if isinstance(location.get(key), str)]
    return '\n\n'.join(dict.fromkeys(part for part in parts if part))


def timezone_for(names: list[str]) -> str | None:
    """The zone whose city part is one of `names` (Lisbon is Europe/Lisbon), so a real city keeps its clock."""
    zones = {zone.rsplit('/', 1)[1].casefold(): zone for zone in sorted(available_timezones(), reverse=True)
             if '/' in zone and not zone.startswith(('Etc/', 'SystemV/', 'US/'))}
    keys = (re.sub(r'\s+', '_', name.strip()).casefold() for name in names)
    return next((zones[key] for key in keys if key in zones), None)


def is_home(location: dict) -> bool:
    name = location.get('name') or ''
    words = set(slug(name).split('-'))
    return location.get('kind') not in REGIONS and bool(POSSESSIVE.match(name)) and bool(words & HOME_WORDS)


def offset(placement, scale: float) -> tuple[float, float] | None:
    """A placement on a parent's 0-100 grid as (lat, lon) offsets in degrees from the parent's centre."""
    if not isinstance(placement, dict):
        return None
    x, y = placement.get('x'), placement.get('y')
    if not all(isinstance(value, (int, float)) and math.isfinite(value) for value in (x, y)):
        return None
    km = STEP_KM * scale
    return round(-(y - 50) * km / 111.0, 5), round((x - 50) * km / 111.0, 5)


class Where(NamedTuple):
    """Where a location sits: its neighbourhood, the home it is part of, and the place or employer it folds into."""
    hood: str
    home: str | None = None
    owner: dict | None = None


class _Map:
    def __init__(self, value: dict, today: str):
        self.value, self.today = value, today
        self.definition = definition_of(value)
        self.types = self.type_labels()
        self.locations, self.children, self.archived = self.tree()
        self.ids: set[str] = set()
        self.hoods: list[dict] = []
        self.places: list[dict] = []
        self.employers: list[dict] = []
        self.lines: dict[str, dict] = {}
        self.inside: dict[str, dict] = {}
        self.roles: dict[str, tuple[str, str]] = {}
        self.entries: list[dict] = []
        self.counts = dict.fromkeys(('streets', 'homes', 'home_rooms', 'rooms', 'links', 'unplaced', 'over'), 0)
        self.homes: list[str] = []
        self.city_name = ''

    # --- Reading the file ---

    def type_labels(self) -> dict[str, str]:
        """Each location's custom type label (City, Shop, Mall), from the optional hierarchy profile."""
        profile = self.value.get('hierarchyProfile') or self.definition.get('hierarchyProfile')
        if not isinstance(profile, dict):
            return {}
        labels = {item.get('id'): item.get('label') for item in profile.get('types') or [] if isinstance(item, dict)}
        chosen = profile.get('locationTypeIds') if isinstance(profile.get('locationTypeIds'), dict) else {}
        return {key: labels[value] for key, value in chosen.items() if isinstance(labels.get(value), str)}

    def tree(self) -> tuple[list[dict], dict, int]:
        """The active locations whose parents are all active, roots first in their order, and children by parent."""
        found = self.definition.get('locations')
        rows = [item for item in found if isinstance(item, dict) and isinstance(item.get('id'), str)] \
            if isinstance(found, list) else []
        seen: set[str] = set()
        rows = [item for item in rows if not (item['id'] in seen or seen.add(item['id']))]  # a repeated id: first wins
        rows.sort(key=lambda item: item.get('sortOrder') if isinstance(item.get('sortOrder'), (int, float)) else 0)
        known = {item['id'] for item in rows}
        children: dict = {}
        for item in rows:
            if item.get('status') != 'archived':
                parent = item.get('parentId') if item.get('parentId') in known else None
                children.setdefault(parent, []).append(item)
        return rows, children, sum(item.get('status') == 'archived' for item in rows)

    def kids(self, location: dict | None) -> list[dict]:
        return self.children.get(location['id'] if location else None, [])

    # --- Records ---

    def uid(self, name: str, fallback: str) -> str:
        base = slug(name) or fallback
        found, number = base, 1
        while found in self.ids:
            number += 1
            found = f'{base[:76]}-{number}'
        self.ids.add(found)
        return found

    def summary(self, location: dict) -> str:
        for key in ('awarenessSummary', 'description'):
            if text(location.get(key)):
                return text(location.get(key), TEXT)
        return text(location.get('name'), TEXT) or 'A place on the map.'

    def lore(self, location: dict, where_line: str) -> None:
        body, name = note_text(location), text(location.get('name'))
        if body and name:
            self.entries.append({'title': name[:160], 'text': f'{where_line}\n\n{body}'.strip()[:lorebooks.MAX_TEXT],
                                 'keywords': [name[:200]], 'always': False, 'enabled': True, 'pattern': False})

    def hood_name(self, hood_id: str) -> str:
        return next(hood['name'] for hood in self.hoods if hood['id'] == hood_id)

    # --- Neighbourhoods ---

    def neighbourhoods(self) -> None:
        roots = self.kids(None)
        if not roots:
            raise DomainError('This world map has no places in it.', 422, 'invalid_city')
        self.city_name = text(roots[0].get('name'), TEXT) or 'My world'
        self.lore(roots[0], '')
        for root in roots:
            self.root(root, root is roots[0])

    def root(self, root: dict, first: bool) -> None:
        """A top region's districts become neighbourhoods; one without districts is a neighbourhood itself."""
        regions = [child for child in self.kids(root) if child.get('kind') in REGIONS]
        if not first:
            self.lore(root, f'A part of {self.city_name}.')
        if not regions:
            hood = self.add_hood(root, None)
            self.roles[root['id']] = ('hood', hood)
            for child in self.kids(root):
                self.visit(child, Where(hood))
            return
        hoods = [(self.add_hood(region, region.get('placement')), region) for region in regions]
        for hood, region in hoods:
            self.roles[region['id']] = ('hood', hood)
            self.lore(region, f'A part of {self.city_name}.')
            for child in self.kids(region):
                self.visit(child, Where(hood))
        for child in self.kids(root):
            if child.get('kind') not in REGIONS:
                self.visit(child, Where(self.nearest(child, hoods)))

    def add_hood(self, location: dict, placement) -> str:
        if len(self.hoods) >= LIMITS['neighborhoods']:
            self.counts['over'] += 1
            return self.hoods[0]['id']
        spot = offset(placement, 1.0)
        self.counts['unplaced'] += spot is None
        lat, lon = spot or (0.0, 0.0)
        self.hoods.append({'id': self.uid(location.get('name') or '', 'neighbourhood'),
                           'name': text(location.get('name'), TEXT) or self.city_name, 'summary': self.summary(location),
                           'vibe': ['local'], 'lat': lat, 'lon': lon, 'housing': ['apartment'],
                           'walkability': 'medium', 'transit': [], 'source': SOURCE})
        return self.hoods[-1]['id']

    def nearest(self, location: dict, hoods: list[tuple[str, dict]]) -> str:
        """A building straight under the city goes in the neighbourhood nearest to it on the city's map."""
        here = offset(location.get('placement'), 1.0)
        placed = [(hood, offset(region.get('placement'), 1.0)) for hood, region in hoods]
        placed = [(hood, spot) for hood, spot in placed if spot]
        if here is None or not placed:
            return hoods[0][0]
        return min(placed, key=lambda item: math.dist(here, item[1]))[0]

    # --- Everything inside a neighbourhood ---

    def visit(self, location: dict, where: Where) -> None:
        role = self.role(location, where)
        self.roles[location['id']] = (role, where.hood)
        self.lore(location, self.where_line(role, where))
        inner = getattr(self, f'as_{role}')(location, where)
        for child in self.kids(location):
            self.visit(child, inner)

    def role(self, location: dict, where: Where) -> str:
        kind = location.get('kind')
        if where.home:
            return 'home_room'
        if is_home(location):
            return 'home'
        if kind in REGIONS:
            return 'street'
        if kind == 'building' and self.kids(location):
            return 'employer'
        return 'place' if kind in ('building', 'place') else 'room'

    def where_line(self, role: str, where: Where) -> str:
        hood = self.hood_name(where.hood)
        if role == 'home_room':
            return f'A room in {where.home}, in {hood}.'
        if role == 'home':
            return f'A home in {hood}, {self.city_name}.'
        return f'In {hood}, {self.city_name}.'

    def as_street(self, location: dict, where: Where) -> Where:
        self.counts['streets'] += 1
        return where

    def as_home(self, location: dict, where: Where) -> Where:
        self.counts['homes'] += 1
        self.homes.append(f"{text(location.get('name'))} ({self.hood_name(where.hood)})")
        return Where(where.hood, text(location.get('name')))

    def as_home_room(self, location: dict, where: Where) -> Where:
        self.counts['home_rooms'] += 1
        return where

    def as_room(self, location: dict, where: Where) -> Where:
        self.counts['rooms'] += 1
        name = text(location.get('name'), TEXT)
        owner = where.owner
        if owner is not None and name:
            folded = self.inside[owner['id']]['rooms'] if owner['id'] in self.inside else owner['spots']
            folded.append(name)
        return where

    def as_employer(self, location: dict, where: Where) -> Where:
        if len(self.employers) >= LIMITS['employers']:
            self.counts['over'] += 1
            return where
        record = {'id': self.uid(location.get('name') or '', 'employer'), 'name': text(location.get('name'), TEXT),
                  'sector': 'business', 'neighborhood': where.hood, 'size': 'medium',
                  'summary': self.summary(location), 'careers': [OFFICE_CAREER], 'source': SOURCE}
        self.employers.append(record)
        self.inside[record['id']] = {'rooms': [], 'kinds': []}
        return Where(where.hood, owner=record)

    def as_place(self, location: dict, where: Where) -> Where:
        if len(self.places) >= LIMITS['places'] or not text(location.get('name')):
            self.counts['over'] += 1
            return where
        kind = self.kind(location)
        record = {'id': self.uid(location['name'], 'place'), 'name': text(location['name'], TEXT), 'kind': kind,
                  'neighborhood': where.hood, 'summary': self.summary(location), 'cost': '$$',
                  'setting': 'outdoor' if kind in OUTDOOR else 'indoor', 'good_for': ['solo', 'friends'],
                  'day_parts': ['evening', 'late'] if kind in EVENING else ['morning', 'afternoon'] if kind == 'cafe'
                  else ['afternoon', 'evening'], 'spots': [], 'source': SOURCE}
        self.places.append(record)
        if where.owner is not None and where.owner['id'] in self.inside:
            self.inside[where.owner['id']]['kinds'].append(kind)
        return Where(where.hood, owner=record)

    def kind(self, location: dict) -> str:
        """The place's kind from its icon, then the words of its name, then its hierarchy type."""
        for char in location.get('icon') or '':
            if char in ICON_KINDS:
                return ICON_KINDS[char]
        for word in slug(location.get('name') or '').split('-'):
            if word in PLACE_KINDS or word in mend.PLACE_KINDS:
                return mend.PLACE_KINDS.get(word, word)
        label = slug(self.types.get(location['id']) or '')
        if label and label not in PLAIN_TYPES:
            return mend.PLACE_KINDS.get(label, label)
        return 'landmark' if location.get('kind') == 'building' else 'attraction'

    # --- Transit ---

    def transit(self) -> None:
        """Labelled links between places people go become lines; links between rooms are walked, not ridden."""
        for location in self.locations:
            if location['id'] not in self.roles:
                continue
            for link in location.get('links') or []:
                if isinstance(link, dict):
                    self.link(location, link)

    def link(self, location: dict, link: dict) -> None:
        label, target = text(link.get('label'), TEXT), self.roles.get(link.get('targetId'))
        ends = (self.roles[location['id']], target)
        if not label or target is None or link.get('state', 'available') != 'available' or \
                any(role in ('room', 'home_room') for role, _ in ends):
            self.counts['links'] += 1
            return
        line = self.lines.get(label.casefold())
        if line is None:
            if len(self.lines) >= LIMITS['transit']:
                self.counts['over'] += 1
                return
            names = list(dict.fromkeys(self.hood_name(hood) for _, hood in ends))
            line = {'id': self.uid(label, 'line'), 'name': label, 'kind': self.line_kind(label),
                    'summary': text(f"A way between {' and '.join(names)}." if len(names) > 1 else
                                    f'A way through {names[0]}.', TEXT), 'source': SOURCE}
            self.lines[label.casefold()] = line
        for hood in self.hoods:
            if hood['id'] in {ends[0][1], ends[1][1]} and line['id'] not in hood['transit'] and len(hood['transit']) < 8:
                hood['transit'].append(line['id'])

    @staticmethod
    def line_kind(label: str) -> str:
        for word in slug(label).split('-'):
            if word in TRANSIT_KINDS or word in mend.TRANSIT_KINDS:
                return mend.TRANSIT_KINDS.get(word, word)
        return 'bus'

    # --- The city ---

    def finish_employers(self) -> None:
        """An employer's jobs follow the places inside it, and its offices and rooms join its summary."""
        careers = catalog.careers()
        for employer in self.employers:
            inside = self.inside[employer['id']]
            hired = [KIND_CAREERS[kind] for kind in inside['kinds'] if kind in KIND_CAREERS]
            # Mostly offices and rooms (a headquarters with a café on one floor) is an office first.
            offices = [OFFICE_CAREER] if len(inside['rooms']) > len(inside['kinds']) or not hired else []
            employer['careers'] = list(dict.fromkeys([*offices, *hired]))
            employer['sector'] = careers.get(employer['careers'][0], {}).get('sector', 'business')
            if inside['rooms']:
                employer['summary'] = text(f"{employer['summary']} Inside: {', '.join(inside['rooms'])}.", TEXT)
        for place in self.places:
            place['spots'] = [spot for spot in dict.fromkeys(place['spots'])][:8]

    def city(self) -> dict:
        roots = self.kids(None)
        zone = timezone_for([text(root.get('name')) for root in roots])
        country = naming.country_for_zone(zone)
        if not self.places:
            self.places.append({'id': self.uid(self.city_name, 'place'), 'name': self.city_name, 'kind': 'landmark',
                                'neighborhood': self.hoods[0]['id'], 'summary': self.summary(roots[0]), 'cost': 'free',
                                'setting': 'outdoor', 'good_for': ['solo', 'friends'],
                                'day_parts': ['afternoon', 'evening'], 'source': SOURCE})
        return {'schema_version': 1, 'id': slug(self.city_name) or 'my-world', 'name': self.city_name,
                'setting': 'original', 'era': 'modern', 'region': zone.split('/')[0] if zone else 'Unknown',
                'country': country or 'Unknown', 'timezone': zone or 'UTC', 'aliases': [], 'summary': self.summary(roots[0]),
                'lat': 0.0, 'lon': 0.0,
                'sources': {SOURCE: {'kind': 'user', 'title': text(f'{lore.MAP_TITLE}{self.map_name()}', TEXT),
                                     'license': 'User content', 'retrieved': self.today}},
                'neighborhoods': self.hoods, 'places': self.places, 'employers': self.employers,
                'transit': list(self.lines.values())}

    def map_name(self) -> str:
        profile = self.value.get('hierarchyProfile') if isinstance(self.value.get('hierarchyProfile'), dict) else {}
        return text(self.value.get('name'), 120) or text(profile.get('name'), 120) or self.city_name[:120]

    def portable_lore(self) -> int:
        """Lorebook entries the export carried along (`portableLore`), in Marinara's keys / content / constant."""
        lore = self.value.get('portableLore') if isinstance(self.value.get('portableLore'), dict) else {}
        items = []
        for book in lore.get('books') or []:
            if isinstance(book, dict) and isinstance(book.get('entries'), (list, dict)):
                found = book['entries']
                items += list(found.values()) if isinstance(found, dict) else found
        for item in lore.get('references') or []:
            items.append(item.get('entry') if isinstance(item, dict) and isinstance(item.get('entry'), dict) else item)
        made = [found for number, item in enumerate(items, 1) if (found := lorebooks.entry(item, 'portable', number))]
        self.entries += made
        return len(made)

    def notes(self, zone: str, carried: int, country: str | None = None) -> list[str]:
        roots, counts = self.kids(None), self.counts
        pictures = self.value.get('artwork')
        read = len(set(self.roles) | {root['id'] for root in roots})
        said = [
            f'Read {read} place{"" if read == 1 else "s"} from the Marinara world map "{self.map_name()}".',
            *([f"{', '.join(text(root.get('name')) for root in roots[1:])} folded in as more neighbourhoods, so the "
               'world stays one town.'] if len(roots) > 1 else []),
            *([f"{counted(counts['streets'], 'street or smaller area', 'streets and smaller areas')} folded into their "
               'neighbourhood; their notes are lore.']
              if counts['streets'] else []),
            *([f"{counted(counts['homes'], 'home', 'homes')} kept as lore, not public places: {'; '.join(self.homes[:8])}."]
              if counts['homes'] else []),
            *([f"{counted(counts['home_rooms'] + counts['rooms'], 'room or floor', 'rooms and floors')} kept as lore and as the spots inside their "
               'building.'] if counts['home_rooms'] + counts['rooms'] else []),
            *([f"{counted(self.archived, 'archived place', 'archived places')} left out."] if self.archived else []),
            *([f"{counted(len(pictures), 'picture', 'pictures')} not imported."] if isinstance(pictures, list) and pictures else []),
            *([f"{counted(counts['links'], 'link', 'links')} without a label, hidden, blocked or between rooms left out; travel is worked "
               'out from distance.'] if counts['links'] else []),
            *([f"{counted(counts['over'], 'place', 'places')} past the city's limits left out."] if counts['over'] else []),
            f'Timezone set to {zone}.' if zone != 'UTC' else
            "No time zone matched the city's name, so it uses UTC; change it in the editor.",
            "Neighbourhood positions are fictional, worked out from the map's layout."
            + (f" Placed at the centre, with no spot on the map: {counts['unplaced']}." if counts['unplaced'] else ''),
            f"The map does not say which country it is in, so it is {country}, from the city's time zone; change it "
            'in the editor.' if country else
            'The map does not say which country it is in; set it in the editor for local holidays.',
        ]
        if carried:
            said.append(f"{counted(carried, 'lorebook entry', 'lorebook entries')} came along with the map.")
        return said


def counted(number: int, one: str, many: str) -> str:
    """"1 picture", "2 pictures"."""
    return f'{number} {one if number == 1 else many}'


def convert(value: dict, today: str) -> dict:
    """{city, book, notes} from a world map: a city definition for the forgiving loader, the world lorebook (or
    None when no location has notes), and what was folded, defaulted or skipped."""
    if not detect(value):
        raise DomainError('This is not a Marinara world map.', 422, 'invalid_city')
    try:
        found = _Map(value, today)
        found.neighbourhoods()
        found.transit()
        found.finish_employers()
        city = found.city()
        carried = found.portable_lore()
    except (TypeError, AttributeError, KeyError, RecursionError) as error:
        # A field of an unexpected type (a number where a name goes) or a chain of places nested past any real map.
        raise DomainError("Part of this world map couldn't be read, so nothing was imported.", 422,
                          'invalid_city') from error
    entries = found.entries[:lorebooks.MAX_ENTRIES]
    book = {'name': found.map_name(), 'description': f'Places in {city["name"]}, from a Marinara world map.',
            'format': BOOK_FORMAT, 'entries': entries} if entries else None
    notes = found.notes(city['timezone'], carried, None if city['country'] == 'Unknown' else city['country'])
    if book:
        notes.append(f"{counted(len(entries), 'lore entry', 'lore entries')} went into the world lorebook \"{book['name']}\".")
    return {'city': city, 'book': book, 'notes': notes}


def free_id(database, wanted: str) -> str:
    """The city's id, numbered when the user already has a city by that name (a map imported twice)."""
    taken = set(catalog.cities()) | set(custom.read(database))
    found, number = wanted, 1
    while found in taken:
        number += 1
        found = f'{wanted[:76]}-{number}'
    return found


def already_in(database, city: dict) -> str | None:
    """The name of a city the user already brought in from this same map (its title and places match)."""
    title, places = city['sources'][SOURCE]['title'], sorted(place['name'] for place in city['places'])
    for saved in custom.read(database).values():
        source = (saved.get('sources') or {}).get(SOURCE) or {}
        if source.get('title') == title and sorted(place['name'] for place in saved.get('places') or []) == places:
            return saved['name']
    return None


def bring(database, value: dict) -> dict:
    """Import a world map straight away: the city joins the user's cities and its lore the world's books."""
    made = convert(value, database.now()[:10])
    same = already_in(database, made['city'])
    require(same is None, f'This world map already came in as {same}. Delete that city first to bring it in again.',
            409)
    city = made['city'] | {'id': free_id(database, made['city']['id'])}
    added = {}

    def with_book(connection, timestamp: str) -> None:
        if made['book']:
            # The notes follow the city into new worlds there and go when it is deleted (dungeon/lore.py).
            added['book'] = lore.add_book(connection, timestamp, made['book'], f"{made['book']['name']}.world-map.json",
                                          city['id'])

    saved = custom.create(database, city, also=with_book)
    return catalog.summary(saved) | {'import_notes': made['notes'] + saved.get('import_notes', []),
                                     'book': added.get('book')}
