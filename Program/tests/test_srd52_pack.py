"""The 5E SRD 5.2.1 content pack (dungeon/rules/packs/srd52/): manifest and attribution, ids, cross-references,
monster math, magic item prices and the economy against wages."""
import json
import re
from pathlib import Path

import pytest

PACK = Path(__file__).resolve().parents[1] / 'dungeon' / 'rules' / 'packs' / 'srd52'
ATTRIBUTION = ('This work includes material from the System Reference Document 5.2.1 ("SRD 5.2.1") by Wizards of '
               'the Coast LLC, available at https://www.dndbeyond.com/srd. The SRD 5.2.1 is licensed under the Creative '
               'Commons Attribution 4.0 International License, available at '
               'https://creativecommons.org/licenses/by/4.0/legalcode.')
LADDER = ('critical_failure', 'failure', 'failure_upside', 'success_cost', 'success', 'critical_success')
RARITY_GP = {'common': 100, 'uncommon': 400, 'rare': 4000, 'very_rare': 40000, 'legendary': 200000}
# Errors printed in the SRD itself, kept as printed and listed in pack.json source_notes.
INITIATIVE_AS_PRINTED = {'gray-ooze', 'invisible-stalker'}  # score is not 10 + modifier
INITIATIVE_BONUS_AS_PRINTED = {'archmage'}  # modifier is not Dex, Dex + PB or Dex + 2 PB
XP_AS_PRINTED = {'archmage'}
SPELL_LISTS_AS_PRINTED = {('Mind Spike', 'Sorcerer'), ('Phantasmal Force', 'Bard'), ('Phantasmal Force', 'Sorcerer'),
                          ('Phantasmal Force', 'Wizard')}


def load(name):
    return json.loads((PACK / name).read_text(encoding='utf-8'))


@pytest.fixture(scope='module')
def pack():
    return {p.stem: json.loads(p.read_text(encoding='utf-8')) for p in sorted(PACK.glob('*.json'))}


def test_manifest_lists_every_file_with_its_count(pack):
    manifest = pack['pack']
    files = {p.name for p in PACK.glob('*.json')} - {'pack.json'}
    assert set(manifest['files']) == files
    for name, count in manifest['files'].items():
        assert len(pack[name.removesuffix('.json')]) == count
    assert manifest['files']['spells.json'] == 339
    assert manifest['files']['monsters.json'] == 330
    assert manifest['files']['magic_items.json'] == 258
    assert manifest['files']['classes.json'] == 12


def test_attribution_is_the_exact_licensed_sentence():
    manifest = load('pack.json')
    assert manifest['license']['id'] == 'CC-BY-4.0'
    assert manifest['license']['attribution'] == ATTRIBUTION
    readme = ' '.join((PACK / 'README.md').read_text(encoding='utf-8').split())
    assert ATTRIBUTION in readme
    assert manifest['changes'], 'CC-BY asks for the changes to be indicated'


def test_outcome_mapping_uses_only_ladder_bands():
    mapping = load('pack.json')['resolution']['outcome_mapping']
    assert mapping['policy'] == 'pass_fail_as_written'
    bands = {k for k in mapping if k in LADDER} | set(mapping['unused_bands'])
    assert bands == set(LADDER)


def test_no_trademarks_in_the_text():
    for path in PACK.glob('*.json'):
        text = path.read_text(encoding='utf-8')
        assert 'D&D' not in text and 'Dungeons & Dragons' not in text and 'Dungeons and Dragons' not in text, path.name


@pytest.mark.parametrize('name', ['classes', 'species', 'backgrounds', 'feats', 'spells', 'magic_items', 'monsters'])
def test_ids_are_unique_slugs(pack, name):
    ids = [e['id'] for e in pack[name]]
    assert len(ids) == len(set(ids))
    assert all(re.fullmatch(r'[a-z0-9]+(-[a-z0-9]+)*', i) for i in ids)


def test_equipment_ids_unique_and_priced(pack):
    items = pack['equipment']['items']
    ids = [e['id'] for e in items]
    assert len(ids) == len(set(ids))
    for e in items:
        if e.get('cost_text') and re.match(r'^[\d,.]+ (CP|SP|EP|GP|PP)$', e['cost_text']):
            assert isinstance(e['cost_cp'], int) and e['cost_cp'] >= 0, e['id']
        assert e.get('shop_types'), e['id']


def test_spells_are_well_formed(pack):
    schools = {'abjuration', 'conjuration', 'divination', 'enchantment', 'evocation', 'illusion', 'necromancy',
               'transmutation'}
    for s in pack['spells']:
        assert 0 <= s['level'] <= 9, s['id']
        assert s['school'] in schools, s['id']
        assert s['classes'], s['id']
        assert s['description'].strip(), s['id']
        assert s['casting_time']['text'] and s['range']['text'] and s['duration']['text'], s['id']


def test_class_spell_lists_match_the_spells_own_classes(pack):
    spells = {s['name']: s for s in pack['spells']}
    on_list = set()
    for c in pack['classes']:
        for level, entries in c.get('spell_list', {}).items():
            for e in entries:
                spell = spells[e['spell']]
                assert spell['level'] == int(level), (c['name'], e['spell'])
                assert c['name'] in spell['classes'], (c['name'], e['spell'])
                on_list.add((e['spell'], c['name']))
    casters = {c['name'] for c in pack['classes'] if c.get('spell_list')}
    named = {(s['name'], k) for s in pack['spells'] for k in s['classes'] if k in casters}
    assert named - on_list == SPELL_LISTS_AS_PRINTED


def test_class_progressions_cover_levels_1_to_20(pack):
    for c in pack['classes']:
        assert [p['level'] for p in c['progression']] == list(range(1, 21)), c['name']
        assert c['hit_die'] in (6, 8, 10, 12), c['name']
        assert len(c['saving_throws']) == 2, c['name']
        assert c['subclass']['features'], c['name']


def dice_average(formula):
    m = re.fullmatch(r'(\d+)d(\d+)(?:([+-])(\d+))?', formula)
    count, die = int(m.group(1)), int(m.group(2))
    bonus = int(m.group(4) or 0) * (-1 if m.group(3) == '-' else 1)
    return count * (die + 1) // 2 + bonus


def test_monster_hit_points_match_their_formula(pack):
    for m in pack['monsters']:
        hp = m['hp']
        if hp.get('formula'):
            assert dice_average(hp['formula']) == hp['average'], m['id']


def test_monster_modifiers_saves_and_initiative(pack):
    for m in pack['monsters']:
        pb = m['proficiency_bonus']
        for ab, v in m['abilities'].items():
            assert v['mod'] == (v['score'] - 10) // 2, (m['id'], ab)
            assert v['save'] in (v['mod'], v['mod'] + pb), (m['id'], ab)
        init = m['initiative']
        if m['id'] not in INITIATIVE_AS_PRINTED:
            assert init['score'] == 10 + init['modifier'], m['id']
        dex = m['abilities']['dex']['mod']
        assert m['id'] in INITIATIVE_BONUS_AS_PRINTED or init['modifier'] in (dex, dex + pb, dex + 2 * pb), m['id']


def test_monster_passive_perception(pack):
    for m in pack['monsters']:
        passive = m['senses'].get('passive_perception')
        perception = m.get('skills', {}).get('Perception', m['abilities']['wis']['mod'])
        assert passive == 10 + perception, m['id']


def test_monster_xp_matches_challenge_rating(pack):
    table = {r['cr']: {int(x) for x in re.findall(r'[\d,]+', r['xp'].replace(',', ''))} for r in pack['rules']['xp_by_cr']}
    for m in pack['monsters']:
        if m['id'] in XP_AS_PRINTED:
            continue
        assert m['xp'] in table[m['cr']], m['id']


def test_magic_item_rarities_and_values(pack):
    rules = {r[0].lower().replace(' ', '_'): r[1] for r in pack['rules']['tables']['magic-item-rarities-and-values']['rows']}
    for rarity, gp in RARITY_GP.items():
        assert rules[rarity] == f'{gp:,} GP'
    scribing = {r['spell_level']: r['cost_cp'] for r in pack['economy']['spell_scroll_scribing']}
    for item in pack['magic_items']:
        assert item['rarity'] in (*RARITY_GP, 'artifact', 'varies'), item['id']
        if item['name'] == 'Spell Scroll':
            for v in item['variants']:
                assert v['value_cp'] == 2 * scribing[v['variant']]
            continue
        half = 2 if item['consumable'] else 1
        for v in item.get('variants') or [item]:
            if v['rarity'] in RARITY_GP:
                assert v['value_cp'] == RARITY_GP[v['rarity']] * 100 // half, item['id']
        if item['rarity'] == 'varies':
            assert item.get('variants'), item['id']


def test_conditions_and_reference_lists(pack):
    rules = pack['rules']
    assert len(rules['conditions']) == 15
    assert len(rules['skills']) == 18
    assert len(rules['damage_types']) == 13
    assert {a['id'] for a in rules['abilities']} == {'str', 'dex', 'con', 'int', 'wis', 'cha'}
    assert [r['level'] for r in rules['character_advancement']] == list(range(1, 21))
    assert len(rules['trinkets']) == 100


def test_lodging_and_meals_are_affordable_on_wages(pack):
    economy = pack['economy']
    wages = {w['id']: w['cp_per_day'] for w in economy['wages']}
    fdl = {e['id']: e['cost_cp'] for e in economy['food_drink_lodging']}
    assert fdl['inn-stay-squalid'] + fdl['meal-squalid'] <= wages['unskilled']
    assert fdl['inn-stay-modest'] <= wages['skilled']
    lifestyles = {e['id']: e['cost_cp_per_day'] for e in economy['lifestyles']}
    assert lifestyles['poor'] <= wages['unskilled'] < lifestyles['modest'] <= wages['skilled']
