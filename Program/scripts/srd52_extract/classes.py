# ruff: noqa: C901
"""Classes: core traits, level table, features, spell lists, subclass, option lists."""
import re

from common import AB_KEY, num, relocate_tables, render, slug, split_label, table_data, unmark

SKILLS = ('Acrobatics', 'Animal Handling', 'Arcana', 'Athletics', 'Deception', 'History', 'Insight', 'Intimidation',
          'Investigation', 'Medicine', 'Nature', 'Perception', 'Performance', 'Persuasion', 'Religion',
          'Sleight of Hand', 'Stealth', 'Survival')


def sections(its, level):
    """[(heading, [items])] split at headings of exactly this level; items before the first are under None."""
    out = [(None, [])]
    for it in its:
        if it[0] == 'h' and it[1] == level:
            out.append((it[2], []))
        else:
            out[-1][1].append(it)
    return out


def core_traits(tbl, d):
    rows = {r[0].strip(): r[1].strip() for r in tbl['rows'] if r and r[0]}
    # "Saving Throw" / "Proficiencies" split over two rows
    if 'Saving Throw' in rows and not rows.get('Proficiencies'):
        rows['Saving Throw Proficiencies'] = rows.pop('Saving Throw')
        rows.pop('Proficiencies', None)
    d['core_traits'] = rows
    d['primary_ability'] = rows.get('Primary Ability')
    m = re.match(r'^D(\d+)', rows.get('Hit Point Die', ''))
    d['hit_die'] = int(m.group(1)) if m else None
    saves = rows.get('Saving Throw Proficiencies', '')
    d['saving_throws'] = [AB_KEY[a] for a in AB_KEY if a in saves]
    sk = rows.get('Skill Proficiencies', '')
    m = re.match(r'^Choose (?:any )?(\d+)', sk)
    if m:
        opts = [s for s in SKILLS if s in sk]
        if sk.startswith('Choose any'):
            opts = list(SKILLS)
        d['skill_choices'] = {'count': int(m.group(1)), 'from': opts}
    d['weapon_proficiencies'] = rows.get('Weapon Proficiencies')
    d['tool_proficiencies'] = rows.get('Tool Proficiencies')
    d['armor_training'] = rows.get('Armor Training')
    d['starting_equipment'] = rows.get('Starting Equipment')


def progression(tbl):
    cols = tbl['columns']
    out = []
    slot_cols = [c for c in cols if re.fullmatch(r'\d', c)]
    for r in tbl['rows']:
        row = dict(zip(cols, r))
        lvl = num(row.get('Level', ''))
        if lvl is None:
            continue
        e = {'level': lvl, 'proficiency_bonus': num(row.get('Proficiency Bonus', '')),
             'features': [f.strip() for f in row.get('Class Features', '').split(',') if f.strip() not in ('', '—')]}
        extra = {}
        for c in cols:
            if c in ('Level', 'Proficiency Bonus', 'Class Features') or c in slot_cols:
                continue
            v = row.get(c, '')
            n = num(v)
            extra[slug(c).replace('-', '_')] = n if n is not None and re.fullmatch(r'[+−-]?\d+', v.strip()) else v
        if extra:
            e['columns'] = extra
        if slot_cols:
            e['spell_slots'] = [num(row[c]) or 0 if row.get(c, '—') not in ('—', '') else 0 for c in slot_cols]
        out.append(e)
    return out


def feature_list(its, owner):
    """Features from '#### Level N: Name' blocks."""
    out = []
    for name, body in sections(its, 4)[1:]:
        m = re.match(r'^Level (\d+): (.+)$', name)
        f = {'name': m.group(2) if m else name}
        if m:
            f['level'] = int(m.group(1))
        f['description'] = render(body)
        tables = [table_data(x[1]) for x in body if x[0] == 'table']
        if tables:
            f['tables'] = tables
        out.append(f)
    return out


def option_list(its):
    out = []
    for name, body in sections(its, 4)[1:]:
        o = {'name': name}
        first = body[0][1] if body and body[0][0] == 'p' else ''
        pm = re.match(r'^\*Prerequisite: (.+)\*$', first)
        if pm:
            o['prerequisite'] = pm.group(1)
            body = body[1:]
        o['description'] = render(body)
        out.append(o)
    return out


def spell_list(its):
    out = {}
    for it in its:
        if it[0] != 'table':
            continue
        cap = it[1]['caption'] or ''
        m = re.search(r'Level (\d)', cap)
        if not m:
            continue
        lvl = int(m.group(1))
        for r in it[1]['rows']:
            if not r or not r[0]:
                continue
            e = {'spell': r[0]}
            if len(r) > 2 and r[2] and r[2] != '—':
                e['special'] = r[2]
            out.setdefault(str(lvl), []).append(e)
    return out


def parse_class(name, its):
    d = {'id': slug(name), 'name': name}
    # tables anywhere in the class: core traits and the features table by caption
    groups = []
    for h, body in sections(its, 3):
        groups.append({'name': h or name, '_items': body})
    relocate_tables(groups)
    for g in groups:
        for it in list(g['_items']):
            if it[0] != 'table':
                continue
            cap = it[1]['caption'] or ''
            if cap == f'Core {name} Traits':
                core_traits(it[1], d)
                g['_items'].remove(it)
            elif cap == f'{name} Features':
                d['features_table'] = table_data(it[1])
                d['progression'] = progression(it[1])
                g['_items'].remove(it)
    d['options'] = {}
    for g in groups:
        h, body = g['name'], g['_items']
        if h.startswith('Becoming a'):
            for sub, sb in sections(body, 4)[1:]:
                key = 'level_1' if 'Level 1' in sub else 'multiclass'
                d.setdefault('becoming', {})[key] = [unmark(x[1]).lstrip('• ').strip() for x in sb if x[0] == 'p']
        elif h == f'{name} Class Features':
            d['features'] = feature_list(body, name)
        elif h == f'{name} Spell List':
            intro = [x for x in body if x[0] == 'p']
            d['spell_list'] = spell_list(body)
            if intro:
                d['spell_list_intro'] = render(intro)
        elif h.startswith(f'{name} Subclass:'):
            sub = h.split(':', 1)[1].strip()
            s = {'id': slug(sub), 'name': sub}
            pre = sections(body, 4)[0][1]
            if pre and pre[0][0] == 'p' and re.match(r'^\*[^*]+\*$', pre[0][1]):
                s['tagline'] = unmark(pre[0][1])
                pre = pre[1:]
            s['description'] = render(pre)
            s['features'] = feature_list(body, sub)
            d['subclass'] = s
        elif h != name:
            d['options'][h] = option_list(body)
    if not d['options']:
        del d['options']
    sc = next((f for f in d.get('features', []) if f['name'] in ('Spellcasting', 'Pact Magic')), None)
    if sc:
        m = re.search(r'(\w+) is your spellcasting ability', unmark(sc['description']))
        d['spellcasting'] = {'feature': sc['name'], 'ability': AB_KEY.get(m.group(1)) if m else None}
        if d['spellcasting']['ability'] is None:
            m = re.search(r'Spellcasting Ability\.?\s*(\w+)', unmark(sc['description']))
            if m and m.group(1) in AB_KEY:
                d['spellcasting']['ability'] = AB_KEY[m.group(1)]
    return d


def parse(its):
    out = []
    for name, body in sections(its, 2)[1:]:
        out.append(parse_class(name, body))
    return out


def label_of(text):
    return split_label(text)[0]
