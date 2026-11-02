"""Check city files before sharing or loading them: `python -m dungeon.world.check FILE_OR_FOLDER ...`.

With no arguments it checks the built-in cities and every pack folder. Each file is validated exactly as
the app loads it; problems are errors (the file will not load) and thin spots are warnings (it loads,
but the companion's days there will repeat). Exits 1 when any file has errors.
"""
import argparse
import json
import sys
from pathlib import Path

from dungeon.world import catalog

FOOD = {'restaurant', 'cafe', 'bar', 'tavern', 'inn', 'market', 'nightlife'}


def warnings(data: dict) -> list[str]:
    """Thin spots that make a city's generated days repetitive, without stopping it loading."""
    found = []
    by_hood = {hood['id']: [] for hood in data['neighborhoods']}
    for place in data['places']:
        by_hood[place['neighborhood']].append(place)
    sparse = sorted(hood for hood, places in by_hood.items() if len(places) < 2)
    if sparse:
        found.append(f'{len(sparse)} neighbourhood(s) with fewer than two places: {", ".join(sparse[:8])}.')
    hungry = sorted(hood for hood, places in by_hood.items() if places and not FOOD & {p['kind'] for p in places})
    if hungry:
        found.append(f'{len(hungry)} neighbourhood(s) with nowhere to eat or drink: {", ".join(hungry[:8])}.')
    if not data['employers'] and not data['career_hubs']:
        found.append('No employers or career hubs, so every job is "a workplace" somewhere.')
    if data['climate'] is None:
        found.append('No climate, so days have no weather.')
    return found


def check_file(path: Path) -> dict:
    # Built-in cities load exactly as written; packs and shared files are mended the way the app loads them.
    builtin = path.resolve().parent == catalog.BUILTIN_CITIES.resolve()
    try:
        data = catalog.prepare(path.read_bytes(), mend=not builtin)
    except (OSError, ValueError) as error:
        return {'file': str(path), 'ok': False, 'errors': [str(error)[:4000]], 'warnings': [], 'adjusted': []}
    return {'file': str(path), 'ok': True, 'id': data['id'], 'name': data['name'], 'errors': [],
            'warnings': warnings(data), 'adjusted': data.get('import_notes', []), 'distribution': data['distribution'],
            'counts': {key: len(data[key]) for key in ('neighborhoods', 'places', 'employers')}}


def targets(paths: list[str]) -> list[Path]:
    if not paths:
        return catalog.city_files(catalog.BUILTIN_CITIES) + [
            file for folder in catalog.pack_dirs() for file in catalog.city_files(folder)]
    found = []
    for item in map(Path, paths):
        found += catalog.city_files(item) if item.is_dir() else [item]
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('paths', nargs='*', help='City files or folders of them (default: built-ins and packs)')
    parser.add_argument('--json', action='store_true', help='Print results as JSON')
    args = parser.parse_args(argv)
    results = [check_file(path) for path in targets(args.paths)]
    ids = [result['id'] for result in results if result['ok']]
    for result in results:
        if result['ok'] and ids.count(result['id']) > 1:
            result['warnings'].append(f'Another checked file also uses the id {result["id"]!r}; only one will load.')
    if args.json:
        print(json.dumps(results, indent=1, ensure_ascii=False))
    else:
        for result in results:
            if result['ok']:
                counts = result['counts']
                print(f'OK    {result["file"]}: {result["name"]} ({counts["neighborhoods"]} neighbourhoods, '
                      f'{counts["places"]} places, {counts["employers"]} employers)')
            else:
                print(f'ERROR {result["file"]}')
            for line in result['errors']:
                print(f'      {line}')
            for line in result.get('adjusted', []):
                print(f'      adjusted: {line}')
            for line in result['warnings']:
                print(f'      warning: {line}')
        if not results:
            print('No city files found.')
    return 1 if any(not result['ok'] for result in results) else 0


if __name__ == '__main__':
    sys.exit(main())
