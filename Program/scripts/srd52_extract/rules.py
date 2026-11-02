# ruff: noqa: C901
"""Rules text: Playing the Game, Character Creation, the Rules Glossary, the Gameplay Toolbox and the
monster rules, as a section tree plus the structured lists code needs (conditions, skills, tables)."""
import re

from classes import sections
from common import money_cp, num, relocate_tables, render, slug, split_label, table_data, unmark


def tree(its, level=2, title=None):
    """Nested sections: {title, text, tables, sections}."""
    parts = sections(its, level)
    node = {'title': title}
    body = parts[0][1]
    node['text'] = render([x for x in body if x[0] != 'h'] if level > 6 else body) if body else ''
    tables = [table_data(x[1]) for x in body if x[0] == 'table']
    if tables:
        node['tables'] = tables
    if level < 6:
        subs = [tree(b, level + 1, h) for h, b in parts[1:]]
        if subs:
            node['sections'] = subs
    if not node['text']:
        del node['text']
    return node


def leaves(its, level):
    """Flatten a chapter into leaf groups for table relocation."""
    out = []

    def walk(items, lvl, prefix):
        parts = sections(items, lvl) if lvl <= 6 else [(None, items)]
        if len(parts) == 1 or lvl > 6:
            out.append({'name': prefix or '', '_items': items})
            return
        out.append({'name': prefix or '', '_items': parts[0][1]})
        for h, b in parts[1:]:
            walk(b, lvl + 1, h)
    walk(its, level, None)
    return out


def regroup(its, level):
    """Relocate floating captioned tables inside a chapter and return the items in order again."""
    groups = []
    cur = {'name': '', '_items': []}
    groups.append(cur)
    for it in its:
        if it[0] == 'h' and it[1] >= level:
            cur = {'name': it[2], '_items': [], 'h': it}
            groups.append(cur)
        else:
            cur['_items'].append(it)
    relocate_tables(groups)
    out = []
    for g in groups:
        if 'h' in g:
            out.append(g['h'])
        out += g['_items']
    return out


def glossary(its):
    out = []
    for name, body in sections(its, 4)[1:]:
        m = re.match(r'^(.+?) \[(.+)\]$', name)
        e = {'id': slug(m.group(1) if m else name), 'name': m.group(1) if m else name}
        if m:
            e['tag'] = m.group(2)
        e['description'] = render(body)
        see = re.findall(r'\*See also\*\s*(.+?)(?:\.$|$)', unmark(e['description']).replace('See also', '*See also*'))
        tables = [table_data(x[1]) for x in body if x[0] == 'table']
        if tables:
            e['tables'] = tables
        effects = []
        for x in body:
            if x[0] == 'p':
                lab, rest = split_label(x[1])
                if lab:
                    effects.append({'name': lab, 'text': rest})
        if effects and e.get('tag') == 'Condition':
            e['effects'] = effects
        del see
        out.append(e)
    return out


def table_index(its):
    out = {}
    for x in its:
        if x[0] == 'table' and x[1].get('caption'):
            out[slug(x[1]['caption'])] = table_data(x[1])
    return out


def poisons(its):
    out = []
    for name, body in sections(its, 4)[1:]:
        m = re.match(r'^(.+) \((.+)\)$', name)
        if not m:
            continue
        d = {'id': slug(m.group(1)), 'name': m.group(1)}
        c = money_cp(m.group(2))
        d['cost_text'] = m.group(2)
        d['cost_cp'] = c
        head = unmark(body[0][1]) if body and body[0][0] == 'p' else ''
        tm = re.match(r'^(Contact|Ingested|Inhaled|Injury) Poison$', head)
        if tm:
            d['type'] = tm.group(1).lower()
            body = body[1:]
        d['description'] = render(body)
        sm = re.search(r'DC (\d+) (\w+) saving throw', unmark(d['description']))
        if sm:
            d['save'] = {'dc': int(sm.group(1)), 'ability': sm.group(2)[:3].lower()}
        d['legality'] = 'restricted'
        d['shop_types'] = ['black_market', 'apothecary']
        out.append(d)
    return out


def traps(its):
    out = []
    for name, body in sections(its, 4)[1:]:
        head = unmark(body[0][1]) if body and body[0][0] == 'p' else ''
        tiers = re.findall(r'(\w+) Trap \(Levels? (\d+)[–-](\d+)\)', head)
        d = {'id': slug(name), 'name': name}
        if tiers:
            d['tiers'] = [{'severity': t[0].lower(), 'levels': [int(t[1]), int(t[2])]} for t in tiers]
            body = body[1:]
        for x in body:
            if x[0] == 'field':
                d[x[1].lower()] = x[2]
        rest = [x for x in body if x[0] != 'field']
        d['description'] = render(rest)
        tables = [table_data(x[1]) for x in rest if x[0] == 'table']
        if tables:
            d['scaling'] = tables
        out.append(d)
    return out


def contagions(its):
    out = []
    for name, body in sections(its, 4)[1:]:
        head = unmark(body[0][1]) if body and body[0][0] == 'p' else ''
        if head != 'Magical Contagion':
            continue
        out.append({'id': slug(name), 'name': name, 'description': render(body[1:])})
    return out


def parse(its, find, until):
    out = {}
    pg = find(its, 'Playing the Game', 1)
    play = regroup(until(its, pg, 1), 2)
    out['playing_the_game'] = tree(play, 2, 'Playing the Game')
    cc = find(its, 'Character Creation', 1)
    create = regroup(until(its, cc, 1), 2)
    out['character_creation'] = tree(create, 2, 'Character Creation')
    tables = {}
    tables.update(table_index(play))
    tables.update(table_index(create))
    rg = find(its, 'Rules Glossary', 1)
    gl = until(its, rg, 1)
    rd = find(gl, 'Rules Definitions', 2)
    out['glossary'] = glossary(until(gl, rd, 2))
    conv = find(gl, 'Glossary Conventions', 2)
    out['glossary_conventions'] = render([x for x in until(gl, conv, 2)[:3]])
    tables.update(table_index(gl))
    tb = find(its, 'Gameplay Toolbox', 1)
    box = regroup(until(its, tb, 1), 2)
    out['gameplay_toolbox'] = tree(box, 2, 'Gameplay Toolbox')
    tables.update(table_index(box))
    mo = find(its, 'Monsters', 1)
    mon = regroup(until(its, mo, 1), 2)
    out['monster_rules'] = tree(mon, 2, 'Monsters')
    tables.update(table_index(mon))
    out['tables'] = tables
    # structured lists
    out['conditions'] = [dict(e) for e in out['glossary'] if e.get('tag') == 'Condition']
    skills = tables.get('skills')
    if skills:
        out['skills'] = [{'id': slug(r[0]), 'name': r[0], 'ability': r[1][:3].lower(), 'example_uses': r[2]}
                         for r in skills['rows']]
    abil = tables.get('ability-descriptions')
    if abil:
        out['abilities'] = [{'id': r[0][:3].lower(), 'name': r[0], 'measures': r[1]} for r in abil['rows']]
    dt = tables.get('damage-types')
    if dt:
        out['damage_types'] = [{'id': r[0].lower(), 'name': r[0], 'examples': r[1]} for r in dt['rows']]
    act = tables.get('actions')
    if act:
        out['actions'] = [{'id': slug(r[0]), 'name': r[0], 'summary': r[1]} for r in act['rows']]
    adv = tables.get('character-advancement')
    if adv:
        out['character_advancement'] = [{'level': int(r[0]), 'xp': int(r[1].replace(',', '')),
                                         'proficiency_bonus': num(r[2])} for r in adv['rows']]
    xp = tables.get('experience-points-by-challenge-rating')
    if xp:
        out['xp_by_cr'] = [{'cr': r[0], 'xp': r[1]} for r in xp['rows']]
    bud = tables.get('xp-budget-per-character')
    if bud:
        out['xp_budget_per_character'] = [{'level': int(r[0]), 'low': int(r[1].replace(',', '')),
                                           'moderate': int(r[2].replace(',', '')), 'high': int(r[3].replace(',', ''))}
                                          for r in bud['rows']]
    tr = tables.get('trinkets')
    if tr:
        out['trinkets'] = [{'roll': r[0], 'trinket': r[1]} for r in tr['rows']]
    secs = dict(sections(box, 2)[1:])
    out['poisons'] = poisons(dict(sections(secs['Poison'], 3)[1:])['Sample Poisons'])
    out['traps'] = traps(dict(sections(secs['Traps'], 3)[1:])['Example Traps'])
    out['contagions'] = contagions(dict(sections(secs['Curses and Magical Contagions'], 3)[1:])['Magical Contagions'])
    return out
