# ruff: noqa: C901
"""Magic Items A–Z."""
import re

from common import relocate_tables, render, slug, table_data, unmark

CATEGORIES = ('Armor', 'Potion', 'Ring', 'Rod', 'Scroll', 'Staff', 'Wand', 'Weapon', 'Wondrous Item')
RARITIES = ('Common', 'Uncommon', 'Rare', 'Very Rare', 'Legendary', 'Artifact')
# Magic Item Rarities and Values table (GP); Artifacts are priceless.
VALUE_GP = {'Common': 100, 'Uncommon': 400, 'Rare': 4000, 'Very Rare': 40000, 'Legendary': 200000}


def type_line(s):
    s = unmark(s.replace('* *', ' ')).strip()
    m = re.match(r'^(' + '|'.join(CATEGORIES) + r')(?: \(([^)]*)\))?, (.+?)(?: \((Requires Attunement[^)]*)\))?$', s)
    if not m:
        raise ValueError(f'magic item type line: {s!r}')
    d = {'category': m.group(1).lower().replace(' ', '_'), 'type_line': s}
    if m.group(2):
        d['subtype'] = m.group(2)
    rar = m.group(3)
    d['rarity_text'] = rar
    found = re.findall(r'(Very Rare|Uncommon|Common|Rare|Legendary|Artifact)(?: \(([^)]*)\))?', rar)
    if 'Varies' in rar:
        d['rarity'] = 'varies'
    elif len(found) == 1:
        d['rarity'] = found[0][0].lower().replace(' ', '_')
    else:
        d['rarity'] = 'varies'
        d['variants'] = [{'variant': v, 'rarity': r.lower().replace(' ', '_')} for r, v in found]
    att = m.group(4)
    d['attunement'] = bool(att)
    if att and ' by ' in att:
        d['attunement_requirement'] = att.split(' by ', 1)[1]
    return d


def consumable(d):
    if d['category'] in ('potion',) or d['category'] == 'scroll' and d['name'] != 'Spell Scroll':
        return True
    return d['category'] == 'weapon' and 'Ammunition' in (d.get('subtype') or '')


def value_cp(rarity, half):
    gp = VALUE_GP.get(rarity.replace('_', ' ').title().replace('Very rare', 'Very Rare'))
    if gp is None:
        return None
    return gp * 100 // (2 if half else 1)


def parse(its):
    items = []
    cur = None
    for it in its:
        if it[0] == 'h' and it[1] <= 4:
            cur = {'name': it[2], '_items': []} if it[1] == 4 else None
            if cur:
                items.append(cur)
            continue
        if cur:
            cur['_items'].append(it)
    relocate_tables(items)
    out = []
    for it in items:
        body = it['_items']
        head = body[0][1]
        d = {'id': slug(it['name']), 'name': it['name']}
        d.update(type_line(head))
        rest = body[1:]
        d['description'] = render(rest)
        tables = [table_data(x[1]) for x in rest if x[0] == 'table']
        if tables:
            d['tables'] = tables
        d['consumable'] = consumable(d)
        if d['rarity'] == 'varies' and 'variants' not in d:
            for t in d.get('tables', []):
                cols = t['columns'] or []
                if 'Rarity' in cols:
                    ri = cols.index('Rarity')
                    ni = 1 if cols[0].startswith('1d') else 0
                    d['variants'] = [{'variant': r[ni], 'rarity': r[ri].lower().replace(' ', '_')} for r in t['rows']]
        if d['rarity'] == 'varies' and 'variants' not in d:
            # each kind is a bold label with its rarity: '**Bronze Griffon (Rare).**'
            kinds = re.findall(r'\*\*([^*(]+?) \((Common|Uncommon|Rare|Very Rare|Legendary)\)\.\*\*', d['description'])
            if kinds:
                d['variants'] = [{'variant': k, 'rarity': r.lower().replace(' ', '_')} for k, r in kinds]
        if 'variants' in d:
            for v in d['variants']:
                v['value_cp'] = value_cp(v['rarity'], d['consumable'])
        elif d['rarity'] not in ('varies', 'artifact'):
            d['value_cp'] = value_cp(d['rarity'], d['consumable'])
        cm = re.search(r'has (\d+) charges', d['description'])
        if cm:
            d['charges'] = int(cm.group(1))
        d['cursed'] = bool(re.search(r'\*\*Curse\.\*\*|\bcursed\b', d['description']))
        sentient = re.search(r'\*\*Sentience\.\*\*', d['description'])
        if sentient:
            d['sentient'] = True
        out.append(d)
    return out
