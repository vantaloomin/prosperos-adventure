"""Rewrite name_sources/us.txt: the US Social Security top 100 given names for each birth year 1880–2008.

Reads the SSA's national baby-name tables (public domain) as mirrored in Hadley Wickham's data-baby-names
repository, which holds each year's top 1000 names by sex up to 2008. The official download
(ssa.gov/oact/babynames/names.zip) is blocked from the build machine; the counts are the same.
Run `python scripts/world/fetch_us_names.py`, then `python scripts/world/given_names.py`.
"""
import csv
import io
import urllib.request
from collections import defaultdict
from pathlib import Path

URL = 'https://raw.githubusercontent.com/hadley/data-baby-names/master/baby-names.csv'
OUT = Path(__file__).resolve().parent / 'name_sources' / 'us.txt'
FIRST, LAST, TOP = 1880, 2008, 100

HEADER = """# id: us
# name: United States
# source: US Social Security Administration, popular baby names (top 100 per year by sex), via github.com/hadley/data-baby-names
# url: https://www.ssa.gov/oact/babynames/
# license: public domain (US government work)
# estimate: no
# estimate-from: 2009
"""


def main():
    with urllib.request.urlopen(URL, timeout=60) as response:
        rows = list(csv.DictReader(io.TextIOWrapper(response, encoding='utf-8')))
    years = defaultdict(list)
    for row in rows:
        year = int(row['year'])
        if FIRST <= year <= LAST:
            years[year, 'F' if row['sex'] == 'girl' else 'M'].append((-float(row['percent']), row['name']))
    lines = [HEADER]
    for year in range(FIRST, LAST + 1):
        for sex in 'FM':
            names = [name for _, name in sorted(years[year, sex])[:TOP]]
            lines.append(f'{year} {sex}: ' + ' '.join(names))
    OUT.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f'Wrote {OUT}')


if __name__ == '__main__':
    main()
