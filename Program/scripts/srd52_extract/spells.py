# ruff: noqa: C901
"""Spells from 'Spell Descriptions'."""
import re

import core
import statblock
from common import AB_KEY, CONDITIONS, damage_list, relocate_tables, render, slug, split_label, table_data, unmark

SCHOOLS = ('Abjuration', 'Conjuration', 'Divination', 'Enchantment', 'Evocation', 'Illusion', 'Necromancy',
           'Transmutation')


def casting_time(s):
    ritual = bool(re.search(r'\bor Ritual\b', s))
    base = re.sub(r'\s*or Ritual\b', '', s).strip()
    d = {'text': s, 'ritual': ritual}
    m = re.match(r'^(Action|Bonus Action|Reaction)(?:,\s*(.*))?$', base)
    if m:
        d['unit'] = m.group(1).lower().replace(' ', '_')
        d['amount'] = 1
        if m.group(2):
            d['trigger'] = m.group(2)
        return d
    m = re.match(r'^(\d+)\s+(minute|minutes|hour|hours)$', base)
    if m:
        d['amount'] = int(m.group(1))
        d['unit'] = m.group(2).rstrip('s')
    return d


def spell_range(s):
    d = {'text': s}
    m = re.match(r'^(\d+)\s+(feet|foot|miles|mile)$', s)
    if m:
        n = int(m.group(1))
        d['feet'] = n * 5280 if m.group(2).startswith('mile') else n
        return d
    m = re.match(r'^(Self|Touch|Sight|Unlimited|Special)(?:\s*\((.+)\))?$', s)
    if m:
        d['kind'] = m.group(1).lower()
        if m.group(2):
            d['area'] = m.group(2)
    return d


def components(s):
    d = {'text': s, 'v': False, 's': False, 'm': False}
    m = re.match(r'^([VSM, ]+?)(?:\s*\((.*)\))?$', s)
    letters = m.group(1) if m else s.split('(')[0]
    for ch in ('V', 'S', 'M'):
        if re.search(r'\b' + ch + r'\b', letters):
            d[ch.lower()] = True
    mat = m.group(2) if m and m.group(2) else None
    if mat:
        d['material'] = mat
        cm = re.search(r'worth ([\d,]+)\+? GP', mat)
        if cm:
            d['material_cost_gp'] = int(cm.group(1).replace(',', ''))
        d['material_consumed'] = 'consume' in mat
    return d


def duration(s):
    d = {'text': s, 'concentration': s.startswith('Concentration')}
    base = re.sub(r'^(?:Concentration,?\s*)?[Uu]p to\s*', '', s)
    m = re.match(r'^(\d+)\s+(round|rounds|minute|minutes|hour|hours|day|days)$', base)
    if m:
        d['amount'] = int(m.group(1))
        d['unit'] = m.group(2).rstrip('s')
    elif base == 'Instantaneous':
        d['unit'] = 'instantaneous'
    return d


def derive(text):
    t = unmark(text)
    d = {}
    saves = sorted({AB_KEY[m] for m in re.findall(
        r'(Strength|Dexterity|Constitution|Intelligence|Wisdom|Charisma) saving throw', t)})
    if saves:
        d['saving_throws'] = saves
    atk = re.findall(r'(melee|ranged) spell attack', t)
    if atk:
        d['attack'] = sorted(set(atk))
    dmg = damage_list(text)
    if dmg:
        d['damage_types'] = sorted({x['type'] for x in dmg})
    conds = sorted({c for c in CONDITIONS if re.search(r'\b' + c + r'\b', t)})
    if conds:
        d['conditions'] = conds
    return d


FIELD_RE = re.compile(r'^\*\*(Casting Time|Range|Components?|Duration):\*\*\s*(.*)$', re.S)
DUR_RE = re.compile(r'^(Instantaneous|Concentration, up to \d+ \w+|\d+ \w+|Until dispelled(?: or triggered)?|Special)'
                    r'\s+(.+)$', re.S)


def normalize(its):
    """A few spells set their header fields in body or table type; turn them back into fields."""
    out = []
    for it in its:
        if it[0] == 'p' and FIELD_RE.match(it[1]):
            m = FIELD_RE.match(it[1])
            val = m.group(2).strip()
            if m.group(1) == 'Duration' and DUR_RE.match(val):
                dm = DUR_RE.match(val)
                out.append(('field', 'Duration', dm.group(1)))
                out.append(('p', dm.group(2), it[2]))
                continue
            out.append(('field', m.group(1), val))
        elif it[0] == 'table' and all(len(r) == 1 and re.match(r'^(Casting Time|Range|Components?|Duration):', r[0])
                                      for r in it[1]['rows']):
            for r in it[1]['rows']:
                lab, val = r[0].split(':', 1)
                out.append(('field', lab, val.strip()))
        else:
            out.append(it)
    return out


def parse(its):
    spells = []
    cur = None
    for it in its:
        if it[0] == 'h' and it[1] == 4:
            cur = {'name': it[2], '_items': []}
            spells.append(cur)
            continue
        if cur is None:
            continue
        cur['_items'].append(it)
    relocate_tables(spells)
    out = []
    for sp in spells:
        out.append(build(sp['name'], sp['_items']))
    blocks = [b for sp in out for b in sp.pop('stat_blocks', [])]
    for b in blocks:
        owners = [sp for sp in out if re.search(r'\b' + re.escape(b['name']) + r'\*{0,2} stat block', sp['description'])]
        if len(owners) != 1:
            raise ValueError(f"stat block {b['name']}: owners {[o['name'] for o in owners]}")
        owners[0].setdefault('stat_blocks', []).append(b)
    return out


def build(name, its):
    d = {'id': slug(name), 'name': name}
    head = its[0][1] if its and its[0][0] == 'p' else ''
    m = re.match(r'^\*(?:Level (\d) (\w+)|(\w+) Cantrip) \((.+)\)\*$', head.strip())
    if not m:
        raise ValueError(f'spell header: {name}: {head!r}')
    d['level'] = int(m.group(1)) if m.group(1) else 0
    d['school'] = (m.group(2) or m.group(3)).lower()
    d['classes'] = [c.strip() for c in m.group(4).split(',')]
    body = []
    statblocks = []
    sb_name = None
    sb_items = []
    for it in normalize(its[1:]):
        if it[0] == 'field':
            key = it[1].lower().replace(' ', '_')
            key = 'components' if key == 'component' else key
            if key == 'casting_time':
                d['casting_time'] = casting_time(it[2])
                d['ritual'] = d['casting_time']['ritual']
            elif key == 'range':
                d['range'] = spell_range(it[2])
            elif key == 'components':
                d['components'] = components(it[2])
            elif key == 'duration':
                d['duration'] = duration(it[2])
                d['concentration'] = d['duration']['concentration']
            continue
        if it[0] == 'h' and it[1] == 3:
            if sb_name:
                statblocks.append(statblock.parse(sb_name, sb_items))
            sb_name, sb_items = it[2], []
            continue
        if sb_name and it[0] == 'p' and core.first(it[2])['f'].startswith('Cambria'):
            statblocks.append(statblock.parse(sb_name, sb_items))
            sb_name, sb_items = None, []
        if sb_name:
            sb_items.append(it)
        else:
            body.append(it)
    if sb_name:
        statblocks.append(statblock.parse(sb_name, sb_items))
    main, higher, upgrade = [], None, None
    for it in body:
        if it[0] == 'p':
            lab, rest = split_label(it[1])
            if lab == 'Using a Higher-Level Spell Slot':
                higher = rest
                continue
            if lab == 'Cantrip Upgrade':
                upgrade = rest
                continue
        main.append(it)
    d['description'] = render(main)
    if higher:
        d['higher_levels'] = higher
    if upgrade:
        d['cantrip_upgrade'] = upgrade
    tables = [table_data(it[1]) for it in main if it[0] == 'table']
    if tables:
        d['tables'] = tables
    if statblocks:
        d['stat_blocks'] = statblocks
    d.update(derive(d['description']))
    return d
