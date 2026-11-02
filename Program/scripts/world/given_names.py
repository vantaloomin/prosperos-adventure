"""Popular given names by birth year, common family names by culture, and names that read as invented.

Run `python scripts/world/given_names.py` to rewrite dungeon/world/data/given_names.json from the text files
in scripts/world/name_sources/ (format in name_sources/FORMAT.md). The United States lists for 1920–2008 are
the Social Security Administration's own tables (`fetch_us_names.py` rewrites them); every other list was
written from general knowledge of each country's published rankings, because the build machine cannot reach
the statistics offices, and is marked as an estimate.
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCES = HERE / 'name_sources'
OUT = HERE.parents[1] / 'dungeon' / 'world' / 'data' / 'given_names.json'
RETRIEVED = '2026-10-05'
PRESENT_YEAR = 2026
# The year each era's present day is set in; a city may set its own `names.year`. Eras missing here
# (medieval, fantasy) have no birth-year lists and use their banks' own names.
ERA_YEARS = {'modern': PRESENT_YEAR, 'other': PRESENT_YEAR, 'future': 2077, 'victorian': 1895, 'steampunk': 1890,
             'frontier': 1885, 'jazz-age': 1926}
LINE = re.compile(r'^(\d{4})(s|-(\d{4}))?\s+([FM]):\s*(.*)$')

# Where a city's country has its own culture here, its residents' `local` names come from it; elsewhere
# (and in made-up countries) the United States lists stand in.
COUNTRIES = {
    'united states': 'us', 'united states of america': 'us', 'usa': 'us', 'us': 'us', 'canada': 'us',
    'united kingdom': 'england-wales', 'uk': 'england-wales', 'great britain': 'england-wales', 'britain': 'england-wales',
    'england': 'england-wales', 'wales': 'england-wales', 'scotland': 'scotland',
    'australia': 'england-wales', 'new zealand': 'england-wales',
    'ireland': 'ireland', 'italy': 'italy', 'mexico': 'mexico', 'spain': 'spain', 'germany': 'germany',
    'austria': 'germany', 'france': 'france', 'belgium': 'france', 'poland': 'poland', 'russia': 'russia',
    'china': 'china', 'taiwan': 'china', 'hong kong': 'china', 'south korea': 'korea', 'korea': 'korea',
    'republic of korea': 'korea',
    'japan': 'japan', 'vietnam': 'vietnam', 'philippines': 'philippines', 'india': 'india',
    'nigeria': 'nigeria', 'ghana': 'ghana', 'jamaica': 'jamaica', 'haiti': 'haiti', 'israel': 'israel',
    'egypt': 'arab', 'lebanon': 'arab', 'jordan': 'arab', 'syria': 'arab', 'iraq': 'arab',
    'saudi arabia': 'arab', 'united arab emirates': 'arab', 'uae': 'arab', 'qatar': 'arab', 'kuwait': 'arab',
}


def words(text: str) -> list[str]:
    return list(dict.fromkeys(word.replace('_', ' ') for word in text.split()))


def read(path: Path) -> tuple[str, dict]:
    header, surnames, cohorts = {}, [], {}
    for raw in path.read_text(encoding='utf-8').splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith('#'):
            key, _, value = line[1:].partition(':')
            header.setdefault(key.strip(), value.strip())
            continue
        if line.startswith('surnames:'):
            surnames += words(line.partition(':')[2])
            continue
        found = LINE.match(line)
        if not found:
            raise ValueError(f'{path.name}: cannot read {line[:40]!r}')
        start = int(found[1])
        end = start + 9 if found[2] == 's' else int(found[3]) if found[3] else start
        cohorts.setdefault((start, end), {})['feminine' if found[4] == 'F' else 'masculine'] = words(found[5])
    estimate_from = 0 if header.get('estimate', 'yes') == 'yes' else int(header.get('estimate-from', 9999))
    note = 'Written from general knowledge of the published rankings; an estimate.' if estimate_from == 0 else ''
    source = {'kind': 'government' if estimate_from else 'curated', 'title': header['source'],
              'license': header.get('license', 'CC0-1.0'), 'retrieved': RETRIEVED, 'url': header.get('url', ''),
              'attribution': '', 'note': note}
    return header['id'], {
        'name': header['name'], 'sources': [source], 'surnames': surnames,
        'cohorts': [{'start': start, 'end': end, 'estimate': start >= estimate_from, **names}
                    for (start, end), names in sorted(cohorts.items())]}


def invented() -> dict:
    found = {'given': [], 'family': []}
    for line in (SOURCES / 'invented.txt').read_text(encoding='utf-8').splitlines():
        key, _, rest = line.partition(':')
        if key in ('given', 'surname') and not line.startswith('#'):
            found['given' if key == 'given' else 'family'] += words(rest)
    return found


def build() -> dict:
    cultures = {}
    for path in sorted(SOURCES.glob('*.txt')):
        if path.name == 'invented.txt':
            continue
        key, culture = read(path)
        if key in cultures:
            # A second file for the same culture (say, recent years) adds its cohorts and sources.
            known = cultures[key]
            known['sources'] += culture['sources']
            known['surnames'] = known['surnames'] or culture['surnames']
            known['cohorts'] = sorted(known['cohorts'] + culture['cohorts'], key=lambda item: item['start'])
        else:
            cultures[key] = culture
    return {'schema_version': 1, 'present_year': PRESENT_YEAR, 'era_years': ERA_YEARS, 'cultures': cultures,
            'countries': {country: key for country, key in COUNTRIES.items() if key in cultures},
            'invented': invented()}


GIVEN_NAMES = build()

if __name__ == '__main__':
    OUT.write_text(json.dumps(GIVEN_NAMES, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    print(f'Wrote {OUT}')
