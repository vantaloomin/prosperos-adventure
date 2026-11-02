"""How others see a person and how they see themselves: two seeded lines built from a phrase bank.

Everyone (townsfolk, other companions living in town, and the companions themselves) gets:

- an "Others see" line, public: how they come across to anyone. Built from one phrase per bank as
  "<temperament>; <a habit you can see>; <how their flaw shows>." It goes in other people's prompts.
- "I see myself" lines, private: one first-person line per facet (who they think they are, their
  temperament, their habit, their flaw, what they want, what lands badly). Only their own prompt has these.

Each facet rolls its own gap by seed, so one person can be blind about their habit, masking their nerves and
perfectly honest about what they want: a *blind spot* (flaw, habit) gives the excuse instead of the owned
fault, a *mask* (temperament) gives what they feel under the face they show, and *hidden depth* (desire,
self-story) gives the bigger story nobody else sees. At most two facets carry a gap, and about one person in
five has none. The model only ever sees the separate lines, never a type label.

Townsfolk read their facets from the sheet they already have (temperament, flaw, desire). People at one place,
or on one street, draw their habit and self-story without replacement, so neighbours don't sound alike. A
companion's lines come from the character form ("How others see them", "How they see themselves") when the
user fills them in, otherwise from word matching on the rest of the sheet, then the seed. The character helper
may pick bank entries by id (`compose`), and every id is checked against the bank.

The bank is data (world/data/perception.json), so it can grow without code changes. No model is involved.
"""
import copy
import json
import re
from functools import cache, lru_cache

from dungeon.world import catalog, generators, personality, townsfolk, wording

FACETS = ('self_story', 'temperament', 'tell', 'flaw', 'desire')
# The gap each facet can carry instead of being aligned.
GAPS = {'temperament': 'mask', 'tell': 'blind_spot', 'flaw': 'blind_spot', 'desire': 'hidden_depth',
        'self_story': 'hidden_depth'}
GAP_CHANCE = 0.27  # Per facet; about one person in five ends up with no gap at all.
MOST_GAPS = 2
PUBLIC_LIMIT = 400
PRIVATE_LIMIT = 1200
# How many meetings before a companion knows each part of a townsperson (dungeon/life/encounters.py).
KNOWS_TELL, KNOWS_SELF = 2, 3


@cache
def bank() -> dict:
    """The phrase bank, checked against the sheet ids the town uses."""
    data = json.loads((catalog.DATA / 'perception.json').read_text(encoding='utf-8'))
    for kind, ids in (('temperaments', townsfolk.TEMPERAMENTS), ('flaws', townsfolk.FLAWS),
                      ('desires', townsfolk.DESIRES)):
        missing = set(ids) - set(data[kind])
        if missing:
            raise ValueError(f'perception.json has no {kind} entry for {", ".join(sorted(missing))}.')
    for kind in ('tells', 'self_stories', 'sore_spots'):
        data[f'{kind}_by_id'] = {entry['id']: entry for entry in data[kind]}
    return data


def ids() -> dict[str, list[str]]:
    """Every id the helper may pick, by facet."""
    found = bank()
    return {'temperament': sorted(found['temperaments']), 'tell': [entry['id'] for entry in found['tells']],
            'flaw': sorted(found['flaws']), 'desire': sorted(found['desires']),
            'self_story': [entry['id'] for entry in found['self_stories']],
            'sore_spot': [entry['id'] for entry in found['sore_spots']]}


def entry(facet: str, entry_id: str) -> dict:
    found = bank()
    if facet in ('temperament', 'flaw', 'desire'):
        return found[f'{facet}s'][entry_id]
    return found[{'tell': 'tells', 'self_story': 'self_stories', 'sore_spot': 'sore_spots'}[facet] + '_by_id'][entry_id]


def phrases(item: dict, field: str, modern: bool) -> list[str]:
    """An entry's phrasings, in period wording where the entry has some and the era is not modern."""
    if not modern and field in (item.get('period') or {}):
        return item['period'][field]
    return item[field]


def phrase(seed: str, label: str, item: dict, field: str, modern: bool) -> str:
    return generators.pick(seed, f'perception-{label}-{field}', phrases(item, field, modern))


def capital(text: str) -> str:
    return text[:1].upper() + text[1:]


def drawn_without_replacement(group: str, index: int, options: list[str], label: str,
                              suits=lambda option: True) -> str:
    """The `index`th person in a group (a place, a street) takes the `index`th option of a shuffle seeded by
    the group, so nobody there shares one until everyone has had one. One whose turn doesn't `suit` them (their
    personality sliders) takes the option half way round instead, which only someone in a group of more than half
    the options could also hold."""
    order = sorted(options, key=lambda option: generators.unit(group, f'perception-{label}', option))
    first, other = order[index % len(order)], order[(index + len(order) // 2) % len(order)]
    return first if suits(first) or not suits(other) else other


def gaps(seed: str) -> dict[str, str]:
    """Each facet's gap or 'aligned', by seed: each rolls on its own, and only the two strongest rolls stand."""
    rolls = sorted((generators.unit(seed, 'perception-gap', facet), facet) for facet in FACETS)
    gapped = {facet for roll, facet in rolls[:MOST_GAPS] if roll < GAP_CHANCE}
    return {facet: GAPS[facet] if facet in gapped else 'aligned' for facet in FACETS}


def build(seed: str, picks: dict[str, str], gap: dict[str, str], modern: bool) -> dict:
    """The two lines from chosen entries: `picks` names an id for every facet plus `sore_spot`, and
    `gap` each facet's gap or 'aligned'."""
    temperament, tell = entry('temperament', picks['temperament']), entry('tell', picks['tell'])
    flaw, desire = entry('flaw', picks['flaw']), entry('desire', picks['desire'])
    story, sore = entry('self_story', picks['self_story']), entry('sore_spot', picks['sore_spot'])
    public = (f"{capital(phrase(seed, 'temperament', temperament, 'seen', modern))}; "
              f"{phrase(seed, 'tell', tell, 'seen', modern)}; {phrase(seed, 'flaw', flaw, 'seen', modern)}.")
    mask = None
    if gap['temperament'] == 'mask' and temperament.get('masks'):
        mask = generators.pick(seed, 'perception-mask', temperament['masks'])
    private = [
        phrase(seed, 'self', story, 'hidden' if gap['self_story'] == 'hidden_depth' else 'lines', modern),
        phrase(seed, 'mask', mask, 'own', modern) if mask else phrase(seed, 'temperament', temperament, 'own', modern),
        phrase(seed, 'tell', tell, 'kind' if gap['tell'] == 'blind_spot' else 'owned', modern),
        phrase(seed, 'flaw', flaw, 'excuse' if gap['flaw'] == 'blind_spot' else 'owned', modern),
        phrase(seed, 'desire', desire, 'hidden' if gap['desire'] == 'hidden_depth' else 'open', modern),
        phrase(seed, 'sore', sore, 'lines', modern),
    ]
    return {'public': public, 'private': private, 'picks': dict(picks), 'gaps': dict(gap),
            'inner': mask['inner'] if mask else None, 'tags': list(tell.get('tags', [])),
            'glimpse': phrase(seed, 'glimpse', story, 'glimpse', modern)}


# Townsfolk ----------------------------------------------------------------------------------------

def group_of(data: dict, sheet: dict) -> tuple[str, int] | None:
    """Who a townsperson draws their habit and self-story alongside: everyone seeded at their place, or
    everyone living on their street, with their position there."""
    parts = sheet['key'].split(':')
    if len(parts) != 4 or parts[0] != 'town' or not parts[3].isdigit():
        return None
    return townsfolk.seed_for(data, f'town:{parts[1]}:{parts[2]}'), int(parts[3])


def for_sheet(data: dict, sheet: dict, edited: dict | None = None) -> dict:
    """A townsperson's lines (or a stepped-back companion's, from the town sheet they live by); `edited`: the
    user's slider changes on their profile."""
    seed, modern = townsfolk.drawn(sheet), townsfolk.modern(data)
    if sheet.get('perception'):
        return wording.regional_all(data, sheet['perception'])
    # Their habit and self-story suit their personality sliders (dungeon/world/personality.py).
    levels = personality.levels_of(personality.for_sheet(seed, sheet, edited))
    options = {facet: personality.fitting(facet, found, levels) for facet, found in ids().items()}
    group = group_of(data, sheet)
    if group:
        everyone = ids()
        tell = drawn_without_replacement(group[0], group[1], everyone['tell'], 'tell',
                                         lambda option: personality.fits('tell', option, levels))
        story = drawn_without_replacement(group[0], group[1], everyone['self_story'], 'self',
                                          lambda option: personality.fits('self_story', option, levels))
    else:
        tell = generators.pick(seed, 'perception-tell', options['tell'])
        story = generators.pick(seed, 'perception-self', options['self_story'])
    picks = {'temperament': sheet['temperament'], 'flaw': sheet['flaw'], 'desire': sheet['desire'], 'tell': tell,
             'self_story': story, 'sore_spot': generators.pick(seed, 'perception-sore', options['sore_spot'])}
    return wording.regional_all(data, build(seed, picks, gaps(seed), modern))


def revealed(data: dict, sheet: dict, times: int) -> dict:
    """What a companion has learned of how a townsperson comes across, by how often they have met: first how
    they come across, then the habit and what sets them off, then a glimpse of how they see themselves. Their
    sore spot never shows directly."""
    found = for_sheet(data, sheet)
    if times < 1:
        return {}
    first = found['public'].split('; ')[0].rstrip('.')
    result = {'comes_across': first + '.'}
    if times >= KNOWS_TELL:
        result['comes_across'] = found['public']
    if times >= KNOWS_SELF and found.get('glimpse'):
        result['says_they_are'] = found['glimpse']
    return result


# Companions -----------------------------------------------------------------------------------------

def words(text: str) -> str:
    return ' ' + re.sub(r"[^a-z0-9']+", ' ', text.casefold().replace('’', "'")) + ' '


@lru_cache(maxsize=4096)
def keyword(word: str) -> str:
    """A bank keyword as whole-word search text. The bank is fixed, so each is normalised once."""
    return f' {words(word).strip()} '


def hits(text: str, keywords) -> int:
    return sum(1 for word in keywords if keyword(word) in text)


def matched(text: str, entries: dict[str, dict], seed: str, label: str) -> str | None:
    """The entry whose keywords the text uses most, ties broken by seed; None when nothing matches. Only the tied
    entries get a seeded draw: a new day asks this for every person around, against every bank entry."""
    scored = [(hits(text, item.get('keywords', ())), key) for key, item in entries.items()]
    top = max((score for score, _key in scored), default=0)
    if top <= 0:
        return None
    return max((generators.unit(seed, f'perception-match-{label}', key), key) for score, key in scored
               if score == top)[1]


def sheet_text(definition: dict) -> dict[str, str]:
    """The parts of a character sheet word matching reads, normalised for whole-word search."""
    lists = {key: ' '.join(definition.get(key) or []) for key in ('skills', 'flaws', 'interests')}
    prose = ' '.join(str(definition.get(key) or '') for key in ('identity', 'personality', 'voice', 'background'))
    return {'flaws': words(lists['flaws']), 'all': words(' '.join([prose, *lists.values()]))}


def rule_picks(definition: dict, seed: str) -> dict[str, str]:
    """Bank entries the sheet's own words point to: flaws from the flaws list first, then anywhere."""
    found, text = bank(), sheet_text(definition)
    picks = {}
    tables = {'temperament': found['temperaments'], 'desire': found['desires'],
              'tell': found['tells_by_id'], 'self_story': found['self_stories_by_id'],
              'sore_spot': found['sore_spots_by_id']}
    flaw = matched(text['flaws'], found['flaws'], seed, 'flaw') or matched(text['all'], found['flaws'], seed, 'flaw')
    if flaw:
        picks['flaw'] = flaw
    for facet, entries in tables.items():
        if pick := matched(text['all'], entries, seed, facet):
            picks[facet] = pick
    return picks


def complete(picks: dict[str, str], seed: str, levels: dict[str, int] | None = None) -> dict[str, str]:
    """Anything still unpicked, drawn by seed from the bank entries that suit the personality sliders (`levels`)."""
    options = ids()
    return {facet: picks.get(facet) or generators.pick(seed, f'perception-{facet}',
                                                       personality.fitting(facet, options[facet], levels))
            for facet in (*FACETS, 'sore_spot')}


def valid_picks(raw) -> dict[str, str]:
    """The helper's picks that name a real bank entry; anything else is dropped."""
    if not isinstance(raw, dict):
        return {}
    options = ids()
    return {facet: value for facet, value in raw.items() if facet in options and value in options[facet]}


def valid_gaps(raw) -> dict[str, str] | None:
    """The helper's gaps, every other facet aligned, at most two; None when it gave none, so the seed decides."""
    if not isinstance(raw, dict):
        return None
    chosen = [facet for facet in FACETS if raw.get(facet) == GAPS[facet]][:MOST_GAPS]
    return {facet: GAPS[facet] if facet in chosen else 'aligned' for facet in FACETS}


def home_data(definition: dict) -> dict | None:
    """The built-in city the sheet names as home, or None."""
    return catalog.cities().get(definition.get('home_city') or '')


def era_modern(definition: dict, city: dict | None = None) -> bool:
    city = city or home_data(definition)
    return city is None or townsfolk.modern(city)


def sliders_of(definition: dict, seed: str) -> dict[str, int]:
    """The personality slider levels the sheet has or rolls (dungeon/world/personality.py)."""
    return personality.levels_of(personality.settle(definition, seed))


def automatic(definition: dict, seed: str, chosen: dict | None = None, chosen_gaps: dict | None = None,
              city: dict | None = None, levels: dict[str, int] | None = None) -> dict:
    """The lines the app gives a companion who has none written: the helper's picks (`chosen`), then the
    sheet's own words, then the seed, among entries that suit their personality sliders (`levels`, else the sheet's
    own). In the home city's own English (`city`, else the built-in city the sheet names): American spelling in the
    United States, like everyone else's lines there."""
    city = city or home_data(definition)
    levels = sliders_of(definition, seed) if levels is None else levels
    picks = complete({**rule_picks(definition, seed), **(chosen or {})}, seed, levels)
    return wording.regional_all(city, build(seed, picks, chosen_gaps or gaps(seed), era_modern(definition, city)))


def compose(definition: dict, seed: str, raw_picks=None, raw_gaps=None, city: dict | None = None) -> dict[str, str]:
    """The form fields for helper picks by id (unknown ids are ignored): what the drafted sheet opens with, in the
    home city's own English (`city`: the drafted companion's home city data)."""
    found = automatic(definition, seed, valid_picks(raw_picks), valid_gaps(raw_gaps), city)
    return {'seen_as': found['public'], 'sees_self': '\n'.join(found['private'])}


def for_companion(companion_id: str, definition: dict) -> dict:
    """A companion's lines: what the user wrote on the form wins, field by field. The same sheet always gives the
    same lines, and a new day asks for every companion's many times over, so they are worked out once per sheet."""
    return copy.deepcopy(lines_for(companion_id, json.dumps(definition, sort_keys=True, default=str)))


@lru_cache(maxsize=512)
def lines_for(companion_id: str, sheet: str) -> dict:
    definition = json.loads(sheet)
    found = automatic(definition, companion_id)
    written_public = (definition.get('seen_as') or '').strip()
    written_private = [line.strip(' -•\t') for line in (definition.get('sees_self') or '').splitlines()
                       if line.strip(' -•\t')]
    return {**found, 'public': written_public or found['public'], 'private': written_private or found['private'],
            'glimpse': None if written_private else found['glimpse'],
            'written': {'seen_as': bool(written_public), 'sees_self': bool(written_private)}}


def suggestions(definition: dict, seed: str, count: int = 6, city: dict | None = None) -> dict:
    """Options for the form's two fields: what a blank field would use, then other bank picks that still fit
    the sheet's words, in the home city's own English (`city`)."""
    levels = sliders_of(definition, seed)
    base = automatic(definition, seed, city=city, levels=levels)
    seen, selves = [base['public']], ['\n'.join(base['private'])]
    for n in range(1, count * 3):
        if len(seen) >= count and len(selves) >= count:
            break
        other = f'{seed}:{n}'
        found = automatic(definition, other, city=city, levels=levels)
        if found['public'] not in seen and len(seen) < count:
            seen.append(found['public'])
        text = '\n'.join(found['private'])
        if text not in selves and len(selves) < count:
            selves.append(text)
    return {'automatic': {'seen_as': base['public'], 'sees_self': '\n'.join(base['private'])},
            'seen_as': seen, 'sees_self': selves}



def own_text(public: str, private: list[str]) -> str:
    """Both lines as they read in the person's own prompt."""
    lines = [f'How others see you (how you come across, whether or not you agree): {public}']
    if private:
        lines.append('How you see yourself (your own private view; others may not see you this way; never '
                     'recite it, let it shape how you react):\n' + '\n'.join(f'- {line}' for line in private))
    return '\n'.join(lines)


MENU = """How others see them and how they see themselves: in "perception", pick one id per facet from these lists \
(only these ids), the one that fits the character best. For "gaps", list only the facets (at most two, often none) \
where how they see themselves differs from how others see them: "mask" for temperament (they show one face and \
feel another), "blind_spot" for tell or flaw (they excuse it), "hidden_depth" for desire or self_story (others \
underestimate them).
temperament (how they come across): {temperament}
tell (a habit people notice): {tell}
flaw: {flaw}
desire: {desire}
self_story (who they think they are): {self_story}
sore_spot (what lands badly): {sore_spot}"""


def menu(levels: dict[str, int] | None = None) -> str:
    """The bank's ids for the quick start's model, which picks by id only: those that suit the personality sliders
    the app rolled (`levels`)."""
    return MENU.format(**{facet: ', '.join(personality.fitting(facet, options, levels))
                          for facet, options in ids().items()})
