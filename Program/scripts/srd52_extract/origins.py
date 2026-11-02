# ruff: noqa: C901
"""Backgrounds, species and feats."""
import re

from classes import SKILLS, sections
from common import AB_KEY, relocate_tables, render, slug, split_label, table_data, unmark


def backgrounds(its):
    out = []
    for name, body in sections(its, 4)[1:]:
        f = {x[1]: x[2] for x in body if x[0] == 'field'}
        if 'Ability Scores' not in f:
            continue
        d = {'id': slug(name), 'name': name,
             'ability_scores': [AB_KEY[a.strip()] for a in f['Ability Scores'].split(',')]}
        feat = f.get('Feat', '')
        m = re.match(r'^(.+?)(?: \((\w+)\))? \(see', feat)
        d['feat'] = {'name': m.group(1), **({'option': m.group(2)} if m.group(2) else {})} if m else {'name': feat}
        d['skill_proficiencies'] = [s for s in SKILLS if s in f.get('Skill Proficiencies', '')]
        d['tool_proficiency'] = re.sub(r'\s*\(see “Equipment”\)', '', f.get('Tool Proficiency', ''))
        d['equipment'] = f.get('Equipment')
        eq = f.get('Equipment', '')
        m = re.match(r'^Choose A or B: \(A\) (.+); or \(B\) (\d+) GP$', eq)
        if m:
            d['equipment_options'] = {'A': [x.strip() for x in re.split(r',\s*', m.group(1))], 'B_gp': int(m.group(2))}
        out.append(d)
    return out


def species(its, all_its):
    groups = [{'name': n, '_items': b} for n, b in sections(its, 4)[1:]]
    # species tables float; pull captioned tables named in the text from the whole chapter
    pool = [it for it in all_its if it[0] == 'table' and it[1].get('caption')]
    for g in groups:
        text = ' '.join(unmark(x[1]) for x in g['_items'] if x[0] == 'p')
        have = {x[1]['caption'] for x in g['_items'] if x[0] == 'table'}
        for t in pool:
            if t[1]['caption'] + ' table' in text and t[1]['caption'] not in have:
                g['_items'].append(t)
                have.add(t[1]['caption'])
    relocate_tables(groups)
    out = []
    for g in groups:
        body = g['_items']
        f = {x[1]: x[2] for x in body if x[0] == 'field'}
        if 'Creature Type' not in f:
            continue
        d = {'id': slug(g['name']), 'name': g['name'], 'creature_type': f['Creature Type'], 'size_text': f['Size']}
        d['size'] = [s for s in ('Small', 'Medium') if s in f['Size']]
        m = re.match(r'^(\d+) feet', f.get('Speed', ''))
        d['speed'] = int(m.group(1)) if m else f.get('Speed')
        traits = []
        intro = []
        for x in body:
            if x[0] == 'field':
                continue
            if x[0] == 'p':
                lab, rest = split_label(x[1])
                if lab:
                    traits.append({'name': lab, 'description': rest, '_tables': []})
                    continue
            if traits:
                if x[0] == 'table':
                    traits[-1]['_tables'].append(x[1])
                    traits[-1]['description'] += '\n\n' + render([x])
                else:
                    traits[-1]['description'] += '\n\n' + render([x])
            else:
                intro.append(x)
        for t in traits:
            tabs = t.pop('_tables')
            if tabs:
                t['tables'] = [table_data(tb) for tb in tabs]
        # a table that sits after the last trait belongs to the trait that names it
        for t in traits:
            for tb in t.get('tables', [])[:]:
                if tb['caption'] and tb['caption'] not in t['description'].split('\n\n')[0]:
                    owner = next((o for o in traits if tb['caption'] + ' table' in o['description']), None)
                    if owner and owner is not t:
                        t['tables'].remove(tb)
                        t['description'] = t['description'].replace('\n\n' + render([('table', tb)]), '')
                        owner.setdefault('tables', []).append(tb)
                        owner['description'] += '\n\n' + render([('table', tb)])
            if 'tables' in t and not t['tables']:
                del t['tables']
        if intro:
            d['intro'] = render(intro)
        d['traits'] = traits
        out.append(d)
    return out


def feats(its):
    out = []
    for cat_name, cat_body in sections(its, 3)[1:]:
        if not cat_name.endswith('Feats'):
            continue
        for name, body in sections(cat_body, 4)[1:]:
            head = unmark(body[0][1]) if body and body[0][0] == 'p' else ''
            m = re.match(r'^(.+?) Feat(?: \(Prerequisite: (.+)\))?$', head)
            d = {'id': slug(name), 'name': name, 'category': (m.group(1) if m else cat_name[:-6]).lower().replace(' ', '_')}
            if m and m.group(2):
                d['prerequisite'] = m.group(2)
            rest = body[1:] if m else body
            d['description'] = render(rest)
            d['repeatable'] = '**Repeatable.**' in d['description']
            asi = re.search(r'\*\*Ability Score Increase\.\*\* (.+)', d['description'])
            if asi:
                d['ability_score_increase'] = asi.group(1).split('\n')[0]
            out.append(d)
    return out
