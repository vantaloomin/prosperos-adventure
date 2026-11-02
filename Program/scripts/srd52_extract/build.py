# ruff: noqa: C901
"""Build the SRD 5.2.1 content pack JSON from the linearized PDF lines."""
import json
import os
import sys

import classes
import core
import equipment
import magic_items
import monsters
import origins
import rules
import spells


def find(its, text, level):
    for i, it in enumerate(its):
        if it[0] == 'h' and it[1] == level and it[2] == text:
            return i
    raise KeyError(text)


def until(its, start, max_level):
    """Items after index start up to the next heading of level <= max_level."""
    out = []
    for it in its[start + 1:]:
        if it[0] == 'h' and it[1] <= max_level:
            break
        out.append(it)
    return out


def scroll_values(items, scribing):
    """A Spell Scroll is worth double its scribing cost (Magic Item Rarities and Values table note)."""
    cost = {r['spell_level']: r['cost_cp'] for r in scribing}
    for d in items:
        if d['name'] == 'Spell Scroll':
            d['consumable'] = True
            for v in d['variants']:
                v['value_cp'] = 2 * cost[v['variant']]
        elif d['consumable'] and d['category'] == 'weapon':
            d['value_unit'] = '10 pieces'


def scrub(obj):
    """Replace the publisher's trademark in running text (CC-BY changes are listed in pack.json)."""
    if isinstance(obj, str):
        return obj.replace('play D&D', 'play').replace('D&D', 'the game')
    if isinstance(obj, list):
        return [scrub(x) for x in obj]
    if isinstance(obj, dict):
        return {k: scrub(v) for k, v in obj.items()}
    return obj


def post(data):
    scroll_values(data['magic_items'], data['economy']['spell_scroll_scribing'])
    for k in data:
        data[k] = scrub(data[k])


ATTRIBUTION = ('This work includes material from the System Reference Document 5.2.1 ("SRD 5.2.1") by Wizards of '
               'the Coast LLC, available at https://www.dndbeyond.com/srd. The SRD 5.2.1 is licensed under the Creative '
               'Commons Attribution 4.0 International License, available at '
               'https://creativecommons.org/licenses/by/4.0/legalcode.')

PACK = {
    'id': 'srd52',
    'name': '5E SRD 5.2.1',
    'ruleset': '5e',
    'version': '5.2.1',
    'compatibility': '5E compatible',
    'source': {
        'document': 'System Reference Document 5.2.1',
        'url': 'https://media.dndbeyond.com/compendium-images/srd/5.2/SRD_CC_v5.2.1.pdf',
        'sha256': '8974902d109d6e63672d7c490bde9ccf052410503d9cfa768237154fbc5e3d87',
        'pages': 364,
    },
    'license': {
        'id': 'CC-BY-4.0',
        'url': 'https://creativecommons.org/licenses/by/4.0/legalcode',
        'attribution': ATTRIBUTION,
    },
    'changes': [
        'Converted from the PDF into structured JSON by Prospero\'s Dungeon (scripts/srd52_extract); the text is '
        'otherwise unchanged apart from the items below.',
        'Removed the publisher\'s game trademark from one sentence in Playing the Game.',
        'Added fields that are not in the source: ids, parsed numbers (prices in copper, weights, dice, saves, '
        'attacks), shop_types, legality, value_cp for magic items (from the Magic Item Rarities and Values table) '
        'and wage classes.',
        'Corrected one printing error, listed under corrections.',
    ],
    'currency': {'unit': 'cp', 'cp': 1, 'sp': 10, 'ep': 50, 'gp': 100, 'pp': 1000},
    'resolution': {
        'die': 'd20',
        'tests': ['ability_check', 'saving_throw', 'attack_roll'],
        'outcome_mapping': {
            'policy': 'pass_fail_as_written',
            'success': 'success',
            'failure': 'failure',
            'critical_success': 'natural 20 on an attack roll or a death saving throw',
            'critical_failure': 'natural 1 on an attack roll or a death saving throw',
            'unused_bands': ['failure_upside', 'success_cost'],
        },
        'referee_questions': ['ability', 'skill', 'dc', 'advantage'],
    },
    'pricing': {
        'magic_item_value': 'value_cp is the rarity value; halved for consumables other than Spell Scroll; a Spell '
                            'Scroll is worth double its scribing cost. Add the base item cost from equipment for '
                            'magic armor and weapons.',
        'wage_classes': 'economy.wages: unskilled = untrained hireling, skilled = skilled hireling (cp per day).',
    },
    'corrections': [
        {'file': 'monsters.json', 'id': 'young-white-dragon', 'field': 'abilities.int.save',
         'printed': '2', 'used': -2, 'why': 'The minus sign is missing; the modifier is -2 and the dragon has no Int '
                                           'save proficiency.'},
    ],
    'source_notes': [
        {'file': 'spells.json', 'id': 'telekinesis', 'note': 'The description ends mid-sentence in the source PDF.'},
        {'file': 'monsters.json', 'id': 'gray-ooze', 'note': 'Initiative is printed as -2 (13); Dex 6 gives -2 (8).'},
        {'file': 'monsters.json', 'id': 'invisible-stalker',
         'note': 'Initiative is printed as +7 (22); +7 gives 17.'},
        {'file': 'monsters.json', 'id': 'archmage',
         'note': 'XP is printed as 8,000; the CR 12 row of the XP table says 8,400. Initiative +7 does not follow '
                 'from Dex +2 and proficiency +4.'},
        {'file': 'classes.json', 'note': 'The Sorcerer spell list omits Mind Spike, and the Bard, Sorcerer and '
                                         'Wizard lists omit Phantasmal Force, though those spells name the classes.'},
    ],
}


def write_pack(data, out_dir):
    pack = dict(PACK)
    pack['files'] = {k + '.json': len(v) for k, v in data.items()}
    with open(os.path.join(out_dir, 'pack.json'), 'w', encoding='utf-8') as f:
        json.dump(pack, f, ensure_ascii=False, indent=1)
        f.write('\n')


def main(lines_path, out_dir):
    lines = core.load(lines_path)
    its = core.items(lines)
    os.makedirs(out_dir, exist_ok=True)
    data = {}
    ci = find(its, 'Classes', 1)
    data['classes'] = classes.parse(until(its, ci, 1))
    co = find(its, 'Character Origins', 1)
    chapter = until(its, co, 1)
    bd = find(chapter, 'Background Descriptions', 3)
    data['backgrounds'] = origins.backgrounds(until(chapter, bd, 3))
    sp = find(chapter, 'Species Descriptions', 3)
    data['species'] = origins.species(until(chapter, sp, 3), chapter)
    fd = find(its, 'Feats', 1)
    data['feats'] = origins.feats(until(its, fd, 1))
    eq = find(its, 'Equipment', 1)
    data['equipment'], data['economy'] = equipment.parse(until(its, eq, 1))
    sd = find(its, 'Spell Descriptions', 2)
    data['spells'] = spells.parse(until(its, sd, 2))
    mi = find(its, 'Magic Items A–Z', 2)
    data['magic_items'] = magic_items.parse(until(its, mi, 1))
    ma = find(its, 'Monsters A–Z', 1)
    data['monsters'] = monsters.parse(its[ma:])
    data['rules'] = rules.parse(its, find, until)
    mc = find(its, 'Magic Items', 1)
    pre = until(its, mc, 1)
    pre = pre[:find(pre, 'Magic Items A–Z', 2)]
    data['rules']['magic_items'] = rules.tree(rules.regroup(pre, 2), 2, 'Magic Items')
    data['rules']['tables'].update(rules.table_index(pre))
    post(data)
    for k, v in data.items():
        with open(os.path.join(out_dir, k + '.json'), 'w', encoding='utf-8') as f:
            json.dump(v, f, ensure_ascii=False, indent=1)
            f.write('\n')
        print(k, len(v))
    write_pack(data, out_dir)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
