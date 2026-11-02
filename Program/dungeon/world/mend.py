"""Mend small mistakes in a city someone wrote, so it loads instead of failing on one wrong word.

User cities and city packs go through `mend` before validation (built-in cities do not: their tests keep them
exact). New words for open lists, such as a new kind of place, a new school type or a new transit line, are
kept as written. A word for a closed list that the generators reason about (costs, times of day, seasons, who
a place suits) is read as the nearest word the app knows. Records that point at something missing are
repointed where the match is clear and left out where it is not. Each change is described in plain words.
"""
import copy
import difflib
import re
import unicodedata
from typing import NamedTuple

from pydantic import ValidationError

from dungeon.world.schema import City

ID = re.compile(r'^[a-z0-9]+(-[a-z0-9]+)*$')
GROUPS = ('neighborhoods', 'places', 'colleges', 'employers', 'career_hubs', 'transit', 'annual_events')
SOURCED = (*GROUPS, 'local_color', 'prices', 'notables')
LISTS = (*SOURCED, 'careers', 'holidays')
SINGULAR = {'neighborhoods': 'neighborhood', 'places': 'place', 'colleges': 'college', 'employers': 'employer',
            'career_hubs': 'career hub', 'transit': 'transit line', 'annual_events': 'event',
            'local_color': 'local color', 'prices': 'price', 'notables': 'notable', 'careers': 'career', 'holidays': 'holiday'}
USER_SOURCE = {'kind': 'user', 'title': 'Written by the user', 'license': 'User content', 'retrieved': '2000-01-01'}
# Keys the app itself adds to a loaded city (a city saved from the API, say), dropped without a note.
LOADER_KEYS = ('data_version', 'builtin', 'origin', 'pack_file', 'revision', 'created_at', 'updated_at', 'import_notes')
# Words people use for the closed lists, mapped to the app's own.
SYNONYMS = {
    'autumn': 'fall',
    'night': 'late', 'late-night': 'late', 'midnight': 'late', 'noon': 'afternoon',
    'lunch': 'afternoon', 'breakfast': 'morning', 'dinner': 'evening',
    'alone': 'solo', 'single': 'solo', 'friend': 'friends', 'group': 'friends', 'groups': 'friends',
    'couple': 'date', 'couples': 'date', 'dates': 'date', 'romantic': 'date', 'kids': 'family', 'families': 'family',
    'children': 'family', 'work': 'coworkers', 'coworker': 'coworkers', 'colleagues': 'coworkers',
    'indoors': 'indoor', 'inside': 'indoor', 'outdoors': 'outdoor', 'outside': 'outdoor', 'both': 'mixed',
    'cheap': '$', 'inexpensive': '$', 'budget': '$', 'moderate': '$$', 'mid': '$$', 'medium': '$$',
    'pricey': '$$$', 'expensive': '$$$', 'luxury': '$$$$', 'very-expensive': '$$$$',
    'average': 'medium', 'moderate-walkability': 'medium', 'huge': 'large', 'big': 'large', 'tiny': 'small',
    'contemporary': 'modern', 'present': 'modern', 'present-day': 'modern', 'historical': 'other',
    'fantasy-medieval': 'fantasy', 'sci-fi': 'future', 'futuristic': 'future', 'cyberpunk': 'future',
    '9-to-5': 'office', 'day': 'office', 'shift': 'shift-day', 'nights': 'shift-night', 'night-shift': 'shift-night',
    'part-time': 'flexible', 'freelance': 'flexible', 'school': 'academic',
    'self-employed': 'freelance', 'freelancer': 'freelance', 'gig': 'freelance', 'gigs': 'freelance',
    'salaried': 'staff', 'employee': 'staff', 'employed': 'staff', 'fixed': 'staff', 'shifts': 'rota',
    'roster': 'rota', 'rotation': 'rota',
}
# Local colour kinds stay open, but these words mean a known one (schema.LOCAL_COLOR_KINDS).
COLOR_KINDS = {'legends': 'legend', 'folklore': 'legend', 'myth': 'legend', 'myths': 'legend', 'folk-tale': 'legend',
               'rumour': 'rumor', 'rumours': 'rumor', 'rumors': 'rumor', 'gossip': 'rumor', 'hearsay': 'rumor',
               'food': 'dish', 'dishes': 'dish', 'drinks': 'drink', 'sayings': 'saying', 'customs': 'custom'}
# Place kinds and transit kinds stay open, but these words mean one the generators already reason about.
PLACE_KINDS = {
    'coffee': 'cafe', 'coffee-shop': 'cafe', 'coffeehouse': 'cafe', 'bakery': 'cafe', 'tea-house': 'cafe',
    'diner': 'restaurant', 'food': 'restaurant', 'eatery': 'restaurant', 'food-truck': 'restaurant',
    'bistro': 'restaurant', 'pub': 'bar', 'brewery': 'bar', 'lounge': 'bar', 'wine-bar': 'bar', 'club': 'nightlife',
    'nightclub': 'nightlife', 'gym': 'fitness', 'pool': 'fitness', 'yoga': 'fitness', 'shop': 'shopping',
    'store': 'shopping', 'mall': 'shopping', 'boutique': 'shopping', 'bookstore': 'shopping', 'theater': 'venue',
    'theatre': 'venue', 'cinema': 'venue', 'concert-hall': 'venue', 'gallery': 'museum', 'zoo': 'attraction',
    'aquarium': 'attraction', 'monument': 'landmark', 'plaza': 'square', 'harbor': 'docks', 'harbour': 'docks',
    'port': 'docks', 'hike': 'trail', 'hiking': 'trail', 'church': 'temple', 'hotel': 'inn', 'arena': 'stadium',
    'farmers-market': 'market', 'botanical-garden': 'garden', 'veterinarian': 'vet', 'veterinary': 'vet',
    'vet-clinic': 'vet', 'veterinary-clinic': 'vet', 'animal-hospital': 'vet', 'pet-clinic': 'vet',
}
TRANSIT_KINDS = {'metro': 'subway', 'underground': 'subway', 'tube': 'subway', 'train': 'commuter-rail',
                 'rail': 'commuter-rail', 'regional-rail': 'commuter-rail', 'tramway': 'tram', 'trolley': 'streetcar',
                 'taxi': 'rideshare', 'uber': 'rideshare', 'lyft': 'rideshare', 'bike': 'bike-share',
                 'bicycle': 'bike-share', 'coach': 'bus', 'driving': 'car', 'walking': 'walk', 'foot': 'walk'}
# Values for fields left out or past saving, by field name.
DEFAULTS = {
    'cost': '$$', 'setting': 'mixed', 'good_for': ['solo', 'friends'], 'day_parts': ['afternoon', 'evening'],
    'vibe': ['local'], 'housing': ['apartment'], 'walkability': 'medium', 'size': 'medium', 'rent_tier': 'mid',
    'type': 'college', 'known_for': ['general-studies'], 'sector': 'general', 'sectors': ['general'],
    'schedule': 'office', 'pay': '$$', 'themes': ['work'], 'kind': 'attraction', 'era': 'other',
    'region': 'Unknown', 'country': 'Unknown', 'timezone': 'UTC', 'schema_version': 1,
    'license': 'Unknown', 'title': 'Untitled source', 'retrieved': '2000-01-01',
}
GROUP_DEFAULTS = {('transit', 'kind'): 'bus', ('local_color', 'kind'): 'other', ('holidays', 'kind'): 'observance',
                  ('sources', 'kind'): 'other', ('', 'setting'): 'original'}
DROP = 'drop'
NUMBERS = {'int_parsing', 'float_parsing', 'int_from_float', 'int_type', 'float_type'}
# Words meaning every value of a list: every time of day, everyone, all year.
EVERY = {'all', 'any', 'anytime', 'all-day', 'everyone', 'year-round', 'all-year'}


def slug(value) -> str:
    text = unicodedata.normalize('NFKD', str(value)).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '-', text).strip('-')[:80].strip('-')


def mend(raw: dict) -> tuple[dict, list[str]]:
    """A copy of `raw` with what can be mended mended, and a sentence for each change. What cannot be mended
    is left for validation to report."""
    mender = _Mender(copy.deepcopy(raw))
    return mender.run(), mender.notes


class _Mender:
    def __init__(self, data: dict):
        self.data = data
        self.notes: list[str] = []

    def note(self, text: str) -> None:
        if text not in self.notes:
            self.notes.append(text)

    def run(self) -> dict:
        if not isinstance(self.data, dict):
            return self.data
        for key in LOADER_KEYS:
            self.data.pop(key, None)
        self.keyed_sources()
        self.open_words()
        for _ in range(40):
            self.references()
            try:
                City.model_validate(self.data)
                return self.data
            except ValidationError as error:
                if not self.fix(error.errors()):
                    return self.data
        return self.data

    # --- Naming ---

    def label(self, group: str, record) -> str:
        if isinstance(record, dict):
            for key in ('name', 'item', 'id'):
                if isinstance(record.get(key), str) and record[key].strip():
                    return record[key].strip()
        return f'a {SINGULAR.get(group, group)}'

    def records(self, group: str) -> list:
        found = self.data.get(group)
        return found if isinstance(found, list) else []

    # --- New words ---

    def open_words(self) -> None:
        """Keep new kinds as written, in the app's id form, unless they plainly mean a kind it reasons about."""
        self.kinds('places', 'kind', PLACE_KINDS)
        self.kinds('transit', 'kind', TRANSIT_KINDS)
        self.kinds('colleges', 'type', {})
        self.kinds('local_color', 'kind', COLOR_KINDS)
        if isinstance(self.data.get('speeds'), dict):
            speeds = {TRANSIT_KINDS.get(slug(key), slug(key)): value for key, value in self.data['speeds'].items()}
            self.data['speeds'] = {key: value for key, value in speeds.items() if key}
        for source in (self.data['sources'].values() if isinstance(self.data.get('sources'), dict) else ()):
            if isinstance(source, dict) and isinstance(source.get('kind'), str):
                source['kind'] = slug(source['kind']) or 'other'

    def keyed_sources(self) -> None:
        """Sources written as a list of records with ids, like every other group, become the table a city keys
        them by. Anything else that is not a table is replaced by `sources()`."""
        if not isinstance(self.data.get('sources'), list):
            return
        keyed = {}
        for number, source in enumerate(self.data['sources'], 1):
            if isinstance(source, dict):
                key = slug(source['id']) if isinstance(source.get('id'), str) else ''
                keyed.setdefault(key or f'source-{number}', {k: v for k, v in source.items() if k != 'id'})
        self.data['sources'] = keyed
        if keyed:
            self.note('Read the sources list as a table keyed by each source\'s id.')

    def kinds(self, group: str, field: str, known: dict) -> None:
        for record in self.records(group):
            if not (isinstance(record, dict) and isinstance(record.get(field), str)):
                continue
            kind = slug(record[field])
            if kind in known:
                self.note(f'{self.label(group, record)}: read the kind "{record[field]}" as "{known[kind]}".')
                kind = known[kind]
            record[field] = kind or GROUP_DEFAULTS.get((group, field), DEFAULTS[field])

    # --- References between records ---

    def references(self) -> None:
        self.sources()
        self.unique()
        hoods = Hoods(self)
        if not hoods.ids:
            return
        for group in ('places', 'colleges', 'employers'):
            for record in self.records(group):
                if isinstance(record, dict) and 'neighborhood' in record:
                    record['neighborhood'] = hoods.find(record['neighborhood'], self.label(group, record)) \
                        or record['neighborhood']
        for event in self.records('annual_events'):
            if isinstance(event, dict) and event.get('neighborhood') is not None:
                found = hoods.find(event['neighborhood'])
                if not found:
                    self.note(f'{self.label("annual_events", event)}: the neighborhood "{event["neighborhood"]}" '
                              'is not in the city, so it happens citywide.')
                event['neighborhood'] = found
        self.hubs(hoods)
        places = {place.get('id') for place in self.records('places') if isinstance(place, dict)}
        self.prune('local_color', 'places', places | set(hoods.ids), 'places')
        self.placed(places)
        self.prune('neighborhoods', 'transit', {line.get('id') for line in self.records('transit')
                                                if isinstance(line, dict)}, 'transit lines')

    def sources(self) -> None:
        if not isinstance(self.data.get('sources'), dict) or not self.data['sources']:
            self.data['sources'] = {'user': dict(USER_SOURCE)}
            self.note('Added a source, "Written by the user", for records that name none.')
        known, first = self.data['sources'], next(iter(self.data['sources']))
        cited = [record for group in SOURCED for record in self.records(group)]
        cited += [self.data['climate']] if isinstance(self.data.get('climate'), dict) else []
        for record in cited:
            if not isinstance(record, dict) or record.get('source') in known:
                continue
            given = record.get('source')
            if isinstance(given, str) and slug(given) in known:
                record['source'] = slug(given)
                continue
            if given:
                self.note(f'{self.label("", record)}: the source "{given}" is not in the sources list, so it cites '
                          f'"{first}".')
            record['source'] = first

    def unique(self) -> None:
        seen = set()
        for group in GROUPS:
            if not isinstance(self.data.get(group), list):
                continue
            kept = []
            for record in self.data[group]:
                key = record.get('id') if isinstance(record, dict) else None
                if isinstance(key, str) and key in seen:
                    self.note(f'Left out a second {SINGULAR[group]} with the id "{key}".')
                    continue
                seen.add(key)
                kept.append(record)
            self.data[group] = kept

    def hubs(self, hoods: 'Hoods') -> None:
        kept = []
        for hub in self.records('career_hubs'):
            if isinstance(hub, dict) and isinstance(hub.get('neighborhoods'), list):
                found = [hoods.find(item) for item in hub['neighborhoods']]
                if None in found:
                    self.note(f'{self.label("career_hubs", hub)}: left out neighborhoods the city does not have.')
                hub['neighborhoods'] = list(dict.fromkeys(item for item in found if item))
                if not hub['neighborhoods']:
                    continue
            kept.append(hub)
        if 'career_hubs' in self.data:
            self.data['career_hubs'] = kept

    def placed(self, places: set) -> None:
        """Leave out notables placed somewhere the city does not have: nowhere clear to put them."""
        kept = []
        for person in self.records('notables'):
            if isinstance(person, dict) and person.get('place') not in places:
                self.note(f'{self.label("notables", person)}: left out, the place "{person.get("place")}" '
                          'is not in the city.')
            else:
                kept.append(person)
        if isinstance(self.data.get('notables'), list):
            self.data['notables'] = kept

    def prune(self, group: str, field: str, known: set, what: str) -> None:
        """Drop references to records the city does not have."""
        for record in self.records(group):
            if isinstance(record, dict) and isinstance(record.get(field), list):
                kept = [key for key in record[field] if key in known]
                if len(kept) != len(record[field]):
                    self.note(f'{self.label(group, record)}: left out {what} the city does not have.')
                record[field] = kept

    def add_hood(self, value: str, named_by: str) -> dict:
        """A neighbourhood a record names that the city lacks, placed at the city's centre."""
        name = value.strip() if slug(value) != value else value.replace('-', ' ').title()
        center = {key: self.data[key] if isinstance(self.data.get(key), (int, float)) else 0.0 for key in ('lat', 'lon')}
        hood = {'id': slug(value), 'name': name[:400], 'summary': f'A part of {self.data.get("name") or "the city"}.',
                'vibe': ['local'], **center, 'housing': ['apartment'], 'walkability': 'medium',
                'source': next(iter(self.data['sources']))}
        self.data['neighborhoods'].append(hood)
        self.note(f'Added the neighborhood "{name}", which {named_by} is in.')
        return hood

    # --- Field by field, from what validation found ---

    def fix(self, errors: list[dict]) -> bool:
        drops, changed = set(), False
        for error in errors:
            loc = tuple(error['loc'])
            outcome = self.fix_one(error, loc)
            if outcome == DROP:
                if self.record_root(loc):
                    drops.add(self.record_root(loc))
                continue
            changed = changed or bool(outcome)
        for root in sorted(drops, key=lambda item: (len(item), item), reverse=True):
            container = self.at(root[:-1])
            group = root[0] if root[0] in SINGULAR else ''
            self.note(f'Left out {self.label(group, container[root[-1]])}: it was missing something it needs.')
            del container[root[-1]]
            changed = True
        return changed

    def record_root(self, loc: tuple):
        if len(loc) >= 2 and loc[0] in LISTS and isinstance(loc[1], int):
            return loc[:2]
        if len(loc) >= 3 and loc[:2] == ('names', 'groups'):
            return loc[:3]
        return None

    def at(self, path: tuple):
        node = self.data
        for key in path:
            node = node[key]
        return node

    def fix_one(self, error: dict, loc: tuple):
        try:
            parent = self.at(loc[:-1]) if loc else None
        except (KeyError, IndexError, TypeError):
            return DROP
        root = self.record_root(loc)
        record = self.at(root) if root else self.data
        group = loc[0] if len(loc) > 1 and isinstance(loc[0], str) else ''
        spot = Spot(error['type'], error.get('input'), error.get('ctx', {}), parent, loc[-1] if loc else None,
                    next((key for key in reversed(loc) if isinstance(key, str)), ''), group, record,
                    self.label(group, record) if root else 'The city')
        handler = HANDLERS.get(spot.kind)
        outcome = handler(self, spot) if handler else False
        return outcome if outcome or not root else DROP

    def extra(self, spot: 'Spot'):
        del spot.parent[spot.key]
        self.note(f'{spot.name}: ignored the field "{spot.key}", which the app does not use.')
        return True

    def literal(self, spot: 'Spot'):
        allowed = re.findall(r"'([^']*)'", spot.ctx.get('expected', ''))
        if isinstance(spot.key, int):
            return self.literal_item(spot, allowed)
        found = self.nearest(spot.value, allowed) or GROUP_DEFAULTS.get((spot.group, spot.field)) \
            or DEFAULTS.get(spot.field)
        found = found if found in allowed else (allowed[0] if allowed else None)
        if found is None:
            return DROP
        spot.parent[spot.key] = found
        self.note(f'{spot.name}: read the {spot.field.replace("_", " ")} "{spot.value}" as "{found}".')
        return True

    def literal_item(self, spot: 'Spot', allowed: list[str]):
        if slug(spot.value) in EVERY:
            spot.parent[:] = [] if spot.field == 'seasons' else allowed
            return True
        found = self.nearest(spot.value, allowed)
        if found is None:
            del spot.parent[spot.key]
            self.note(f'{spot.name}: left out "{spot.value}" from {spot.field.replace("_", " ")}.')
        else:
            spot.parent[spot.key] = found
            self.note(f'{spot.name}: read "{spot.value}" as "{found}".')
        return True

    def pattern(self, spot: 'Spot'):
        fixed = slug(spot.value) if isinstance(spot.value, str) else ''
        if fixed:
            spot.parent[spot.key] = fixed
        elif isinstance(spot.key, int):
            del spot.parent[spot.key]
        else:
            return DROP
        return True

    def missing(self, spot: 'Spot'):
        fallback = self.default(spot.group, spot.field, spot.record)
        if fallback is None:
            return DROP
        spot.parent[spot.key] = fallback
        if spot.kind != 'missing' or spot.field not in ('source', 'summary'):
            self.note(f'{spot.name}: filled in {spot.field.replace("_", " ")} as {fallback!r}.')
        return True

    def too_long(self, spot: 'Spot'):
        limit = spot.ctx['max_length']
        if isinstance(spot.value, list):
            self.note(f'{spot.name}: kept the first {limit} {spot.field.replace("_", " ")}.')
        spot.parent[spot.key] = spot.value[:limit]
        return True

    def bound(self, spot: 'Spot'):
        limit = next(iter(spot.ctx.values()), None)
        if isinstance(limit, (int, float)):
            spot.parent[spot.key] = limit
            return True
        return False

    def coerce(self, spot: 'Spot'):
        if spot.kind == 'list_type' and isinstance(spot.value, str):
            spot.parent[spot.key] = [item.strip() for item in spot.value.split(',') if item.strip()]
            return True
        if spot.kind == 'string_type' and isinstance(spot.value, (int, float)):
            spot.parent[spot.key] = str(spot.value)
            return True
        number = re.search(r'-?\d+(\.\d+)?', str(spot.value))
        if spot.kind in NUMBERS and number:
            spot.parent[spot.key] = float(number.group()) if 'float' in spot.kind else round(float(number.group()))
            return True
        return False

    def rule(self, spot: 'Spot'):
        """A record's own check failed: a rent running high to low, a price backwards, a month out of range."""
        record = spot.record if isinstance(spot.record, dict) else {}
        if spot.field == 'rent':
            spot.parent[spot.key] = None
            self.note(f'{spot.name}: left out a rent range that did not run low to high.')
            return True
        if spot.group == 'prices':
            record['low'], record['high'] = sorted((record.get('low', 0), record.get('high', 0)))
            return True
        if spot.group == 'annual_events' and isinstance(record.get('months'), list):
            record['months'] = [month for month in record['months'] if isinstance(month, int) and 1 <= month <= 12]
            return bool(record['months'])
        return False

    def nearest(self, value, allowed: list[str]):
        if not isinstance(value, str) or not allowed:
            return None
        word = slug(value)
        if value.strip() in allowed:
            return value.strip()
        if word in allowed:
            return word
        if '$' in value and '$' in allowed:
            return '$' * min(value.count('$'), 4)
        mapped = SYNONYMS.get(word)
        if mapped in allowed:
            return mapped
        close = difflib.get_close_matches(word, allowed, n=1, cutoff=0.75)
        return close[0] if close else None

    def default(self, group: str, field: str, record):
        if field == 'source':
            return next(iter(self.data['sources']))
        if field in ('summary', 'name', 'item') and isinstance(record, dict):
            label = self.label(group, record)
            if field == 'name' and isinstance(record.get('id'), str):
                return record['id'].replace('-', ' ').capitalize()
            return label if not label.startswith('a ') else None
        if field == 'id' and isinstance(record, dict) and isinstance(record.get('name'), str):
            return slug(record['name']) or None
        if field in ('lat', 'lon'):
            hoods = [hood[field] for hood in self.records('neighborhoods') if isinstance(hood, dict)
                     and isinstance(hood.get(field), (int, float))]
            own = self.data.get(field)
            if group == 'neighborhoods' and isinstance(own, (int, float)):
                return own
            return round(sum(hoods) / len(hoods), 4) if hoods else 0.0
        if field == 'neighborhood' and group in ('colleges', 'employers'):
            return None
        if field == 'summary' and group == '':
            return self.data.get('name') if isinstance(self.data.get('name'), str) else None
        found = GROUP_DEFAULTS.get((group, field), DEFAULTS.get(field))
        return copy.deepcopy(found)


class Spot(NamedTuple):
    """Where one validation error is: what kind, the value, its container and key, and the record it is in."""
    kind: str
    value: object
    ctx: dict
    parent: object
    key: object
    field: str
    group: str
    record: object
    name: str


class Hoods:
    """The city's neighbourhoods by id and by name, finding one a record names or adding it."""

    def __init__(self, mender: _Mender):
        self.mender = mender
        self.ids = {hood['id'] for hood in mender.records('neighborhoods')
                    if isinstance(hood, dict) and isinstance(hood.get('id'), str)}
        self.names = {slug(hood.get('name', '')): hood['id'] for hood in mender.records('neighborhoods')
                      if isinstance(hood, dict) and hood.get('id') in self.ids}

    def find(self, value, add_for: str | None = None) -> str | None:
        word = slug(value) if isinstance(value, str) else ''
        if not word:
            return None
        if value in self.ids or word in self.ids:
            return value if value in self.ids else word
        if word in self.names:
            return self.names[word]
        close = difflib.get_close_matches(word, [*self.ids, *self.names], n=1, cutoff=0.85)
        if close:
            return self.names.get(close[0], close[0])
        if add_for is None:
            return None
        self.mender.add_hood(value, add_for)
        self.ids.add(word)
        return word


HANDLERS = {
    'extra_forbidden': _Mender.extra, 'literal_error': _Mender.literal, 'string_pattern_mismatch': _Mender.pattern,
    'missing': _Mender.missing, 'string_too_short': _Mender.missing, 'too_short': _Mender.missing,
    'none_required': _Mender.missing, 'string_too_long': _Mender.too_long, 'too_long': _Mender.too_long,
    'greater_than_equal': _Mender.bound, 'less_than_equal': _Mender.bound, 'greater_than': _Mender.bound,
    'less_than': _Mender.bound, 'list_type': _Mender.coerce, 'string_type': _Mender.coerce,
    'int_parsing': _Mender.coerce, 'float_parsing': _Mender.coerce, 'int_from_float': _Mender.coerce,
    'int_type': _Mender.coerce, 'float_type': _Mender.coerce, 'value_error': _Mender.rule,
}
