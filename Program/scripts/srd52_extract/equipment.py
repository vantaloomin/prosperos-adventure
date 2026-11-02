# ruff: noqa: C901
"""Equipment chapter: the item catalog (weapons, armor, tools, gear, mounts, vehicles) and the economy
(coins, lifestyles, food and lodging, hirelings, spellcasting services, crafting costs)."""
import re

from classes import sections
from common import money_cp, render, slug, split_label, table_data, unmark, weight_lb

# Which kinds of shop stock an item. Our own tagging for stock generation, not SRD text.
SHOP_RULES = (
    (r'^(Acid|Alchemist’s Fire|Antitoxin|Oil|Perfume|Vial|Bottle, Glass|Flask)$', ['apothecary', 'general_store']),
    (r'^Poison', ['black_market', 'apothecary']),
    (r'^Potion of Healing$', ['apothecary', 'temple']),
    (r'^(Holy Water|Holy Symbol|Healer’s Kit)', ['temple', 'apothecary']),
    (r'^Spell Scroll', ['magic_shop', 'bookseller']),
    (r'^(Book|Ink|Ink Pen|Paper|Parchment|Map|Case, Map or Scroll|Sealing Wax)', ['bookseller', 'general_store']),
    (r'^(Clothes|Costume|Robe)', ['tailor', 'general_store']),
    (r'^(Arcane Focus|Component Pouch|Druidic Focus)', ['magic_shop']),
    (r'(Pack)$', ['general_store']),
    (r'^(Lock|Manacles|Lantern|Lamp|Magnifying Glass|Spyglass|Signal Whistle|Hunting Trap|Mirror|Tinderbox)',
     ['tinker', 'general_store']),
    (r'^(Chain|Caltrops|Ball Bearings|Spikes, Iron|Pot, Iron|Crowbar|Grappling Hook|Shovel|Bucket|Bell)',
     ['smith', 'general_store']),
)


def shop_types(item):
    cat = item['category']
    if cat == 'weapon':
        if item.get('firearm'):
            return ['gunsmith']
        if item['weapon_type'] == 'ranged' or 'Ammunition' in item.get('property_names', []):
            return ['bowyer', 'weaponsmith']
        return ['weaponsmith', 'smith']
    if cat == 'armor':
        if item['name'] in ('Padded Armor', 'Leather Armor', 'Studded Leather Armor', 'Hide Armor'):
            return ['leatherworker', 'armorer']
        return ['armorer', 'smith']
    if cat == 'ammunition':
        return ['bowyer', 'general_store'] if 'Bullets, Firearm' not in item['name'] else ['gunsmith']
    if cat == 'tool':
        return ['general_store', 'tinker'] if item.get('tool_type') != 'artisan' else ['general_store', 'smith']
    if cat == 'mount':
        return ['stable']
    if cat in ('service', 'animal_feed'):
        return ['stable']
    if cat in ('tack', 'drawn_vehicle'):
        return ['stable', 'cartwright']
    if cat == 'vehicle':
        return ['shipwright']
    for pat, shops in SHOP_RULES:
        if re.search(pat, item['name']):
            return shops
    return ['general_store']


def cost_fields(d, cost):
    d['cost_text'] = cost
    c = money_cp(cost)
    if c is not None:
        d['cost_cp'] = c


def weight_fields(d, w):
    if w is None:
        return
    d['weight_text'] = w
    lb = weight_lb(w.replace('½', '.5') if re.match(r'^\d+½', w) else w)
    if lb is not None:
        d['weight_lb'] = lb


def frac(s):
    s = s.strip()
    if s.endswith('½'):
        return (float(s[:-1]) if s[:-1] else 0) + 0.5
    if '/' in s:
        a, b = s.split('/')
        return int(a) / int(b)
    return float(s.replace(',', ''))


def weapon_property(p):
    p = p.strip()
    m = re.match(r'^(Ammunition|Thrown) \(Range (\d+)/(\d+)(?:; (\w+))?\)$', p)
    if m:
        d = {'name': m.group(1), 'range': int(m.group(2)), 'range_long': int(m.group(3))}
        if m.group(4):
            d['ammunition'] = m.group(4)
        return d
    m = re.match(r'^Versatile \((\d+d\d+)\)$', p)
    if m:
        return {'name': 'Versatile', 'damage': m.group(1)}
    m = re.match(r'^(.+?) \((.+)\)$', p)
    if m:
        return {'name': m.group(1), 'note': m.group(2)}
    return {'name': p}


def weapons(tbl):
    out = []
    cat = None
    for r in tbl['rows']:
        if r[0] and not any(r[1:]):
            cat = r[0]
            continue
        name, dmg, props, mastery, w, cost = r[:6]
        d = {'id': slug(name), 'name': name, 'category': 'weapon'}
        m = re.match(r'^(Simple|Martial) (Melee|Ranged) Weapons$', cat or '')
        d['weapon_category'] = m.group(1).lower()
        d['weapon_type'] = m.group(2).lower()
        dm = re.match(r'^(\d+(?:d\d+)?) (\w+)$', dmg)
        d['damage'] = {'dice': dm.group(1), 'type': dm.group(2).lower()} if dm else {'text': dmg}
        plist = [] if props.strip() in ('—', '') else [weapon_property(p) for p in re.split(r',\s*(?![^()]*\))', props)]
        d['properties'] = plist
        d['property_names'] = [p['name'] for p in plist]
        d['mastery'] = mastery
        if name in ('Musket', 'Pistol'):
            d['firearm'] = True
        weight_fields(d, w)
        cost_fields(d, cost)
        out.append(d)
    return out


def armor(tbl):
    out = []
    cat = don = doff = None
    for r in tbl['rows']:
        if r[0] and not any(r[1:]):
            m = re.match(r'^(Light|Medium|Heavy) Armor \((.+)\)$', r[0])
            if m:
                cat = m.group(1).lower()
                times = m.group(2)
                tm = re.findall(r'(\d+) Minutes? to (Don(?: or Doff)?|Doff)', times)
                for n, what in tm:
                    if 'Don' in what:
                        don = int(n)
                    if 'Doff' in what:
                        doff = int(n)
            else:
                cat, don, doff = 'shield', None, None
            continue
        name, ac, strength, stealth, w, cost = r[:6]
        d = {'id': slug(name), 'name': name, 'category': 'armor', 'armor_type': cat}
        m = re.match(r'^(\d+)(?: \+ Dex modifier(?: \(max (\d)\))?)?$', ac)
        if cat == 'shield':
            d['ac_bonus'] = int(ac.replace('+', ''))
        elif m:
            d['ac_base'] = int(m.group(1))
            d['dex_bonus'] = 'Dex' in ac
            if m.group(2):
                d['dex_max'] = int(m.group(2))
        d['ac_text'] = ac
        sm = re.match(r'^Str (\d+)$', strength)
        if sm:
            d['strength_required'] = int(sm.group(1))
        d['stealth_disadvantage'] = stealth == 'Disadvantage'
        if don:
            d['don_minutes'] = don
            d['doff_minutes'] = doff
        weight_fields(d, w)
        cost_fields(d, cost)
        out.append(d)
    return out


def tools(its):
    out = []
    kind = None
    for it in its:
        if it[0] == 'h' and it[1] == 3:
            kind = 'artisan' if it[2] == 'Artisan’s Tools' else 'other'
    for h3, body in sections(its, 3)[1:]:
        if h3 not in ('Artisan’s Tools', 'Other Tools'):
            continue
        kind = 'artisan' if h3 == 'Artisan’s Tools' else 'other'
        for name, tb in sections(body, 4)[1:]:
            m = re.match(r'^(.+?) \((.+)\)$', name)
            nm, cost = m.group(1), m.group(2)
            f = {x[1]: x[2] for x in tb if x[0] == 'field'}
            d = {'id': slug(nm), 'name': nm, 'category': 'tool', 'tool_type': kind,
                 'ability': f.get('Ability', '').lower()[:3] or None}
            cost_fields(d, cost)
            weight_fields(d, f.get('Weight'))
            d['utilize'] = f.get('Utilize')
            if f.get('Craft'):
                d['craft'] = [x.strip() for x in re.split(r',\s*(?![^()]*\))', f['Craft'])]
            if f.get('Variants'):
                d['variants'] = []
                for v in re.split(r',\s*(?![^()]*\))', f['Variants']):
                    vm = re.match(r'^(.+?) \(([^,)]+)(?:, ([^)]+))?\)$', v.strip())
                    if vm:
                        e = {'name': vm.group(1)[0].upper() + vm.group(1)[1:]}
                        cost_fields(e, vm.group(2))
                        if vm.group(3):
                            weight_fields(e, vm.group(3))
                        d['variants'].append(e)
            rest = [x for x in tb if x[0] != 'field']
            if rest:
                d['description'] = render(rest)
            out.append(d)
    return out


def gear(its):
    """Adventuring Gear: table rows joined with the descriptions under '#### Name (Cost)'."""
    tables = [x[1] for x in its if x[0] == 'table']
    main = next(t for t in tables if t['caption'] == 'Adventuring Gear')
    desc = {}
    sub_tables = {}
    for name, body in sections(its, 4)[1:]:
        m = re.match(r'^(.+?) \((.+)\)$', name)
        key = m.group(1) if m else name
        desc[key] = [x for x in body if x[0] != 'table']
        for x in body:
            if x[0] == 'table' and x[1]['caption'] != 'Adventuring Gear':
                sub_tables.setdefault(key, []).append(x[1])
    out = []
    for r in main['rows']:
        name, w, cost = r[:3]
        base = re.sub(r' \((Cantrip|Level 1)\)$', '', name)
        d = {'id': slug(name), 'name': name, 'category': 'gear'}
        weight_fields(d, w)
        cost_fields(d, cost)
        body = desc.get(name) or desc.get(base)
        if body:
            d['description'] = render(body)
        if name.endswith('Pack') and body:
            cm = re.search(r'contains the following items: (.+)\.', unmark(d['description']))
            if cm:
                d['contents'] = [x.strip() for x in re.split(r',\s*(?:and\s+)?', cm.group(1))]
        if name.startswith('Poison'):
            d['legality'] = 'restricted'
        if name in ('Potion of Healing',) or name.startswith('Spell Scroll'):
            d['magic'] = True
        if name == 'Ammunition':
            d['see_category'] = 'ammunition'
        if name in ('Arcane Focus', 'Druidic Focus', 'Holy Symbol'):
            # priced per variant in the sub-table
            d['variants'] = []
            for t in sub_tables.get(name, []):
                for vr in t['rows']:
                    e = {'name': vr[0]}
                    if len(vr) == 3:
                        weight_fields(e, vr[1])
                        cost_fields(e, vr[2])
                    d['variants'].append(e)
        out.append(d)
    amm = next((t for t in tables if t['caption'] == 'Ammunition'), None)
    if amm:
        for r in amm['rows']:
            typ, amount, storage, w, cost = r[:5]
            d = {'id': slug(typ), 'name': typ, 'category': 'ammunition', 'bundle': int(amount), 'storage': storage}
            weight_fields(d, w.replace('1½', '1.5'))
            if 'weight_lb' not in d:
                d['weight_lb'] = frac(w.split(' ')[0])
            cost_fields(d, cost)
            out.append(d)
    return out


def mounts(its):
    out = []
    tables = {x[1]['caption']: x[1] for x in its if x[0] == 'table'}
    for r in tables['Mounts and Other Animals']['rows']:
        d = {'id': slug(r[0]), 'name': r[0], 'category': 'mount',
             'carrying_capacity_lb': int(r[1].split(' ')[0].replace(',', ''))}
        cost_fields(d, r[2])
        out.append(d)
    parent = None
    for r in tables['Tack, Harness, and Drawn Vehicles']['rows']:
        if r[0] and not r[1] and not r[2]:
            parent = r[0]
            continue
        name = f'{parent}, {r[0]}' if parent and r[0] in ('Exotic', 'Military', 'Riding') else r[0]
        if r[0] not in ('Exotic', 'Military', 'Riding'):
            parent = None
        cat = 'drawn_vehicle' if r[0] in ('Carriage', 'Cart', 'Chariot', 'Sled', 'Wagon') else 'tack'
        if r[0] in ('Feed per day', 'Stabling per day'):
            cat = 'service' if r[0].startswith('Stabling') else 'animal_feed'
        d = {'id': slug(name), 'name': name, 'category': cat}
        weight_fields(d, r[1])
        cost_fields(d, r[2])
        out.append(d)
    for r in tables['Airborne and Waterborne Vehicles']['rows']:
        ship, speed, crew, pas, cargo, ac, hp, dt, cost = r[:9]
        d = {'id': slug(ship), 'name': ship, 'category': 'vehicle', 'speed_mph': frac(speed.split(' ')[0]),
             'crew': int(crew), 'passengers': 0 if pas == '—' else int(pas),
             'cargo_tons': 0 if cargo == '—' else frac(cargo), 'ac': int(ac), 'hp': int(hp),
             'damage_threshold': None if dt == '—' else int(dt), 'airborne': ship == 'Airship'}
        cost_fields(d, cost)
        out.append(d)
    return out


def economy(chapter):
    eco = {}
    co = next(x[1] for x in chapter if x[0] == 'table' and x[1]['caption'] == 'Coin Values')
    eco['coins'] = []
    for r in co['rows']:
        m = re.match(r'^(.+) \((\w\w)\)$', r[0])
        eco['coins'].append({'name': m.group(1), 'abbr': m.group(2), 'cp': int(round(frac(r[1]) * 100))})
    eco['selling'] = 'Equipment fetches half its cost when sold. Trade goods and valuables (gems, art objects) ' \
                     'keep their full value.'
    secs = dict(sections(chapter, 2)[1:])
    life = []
    for name, body in sections(secs['Lifestyle Expenses'], 3)[1:]:
        m = re.match(r'^(\w+) \((Free|(\d+) (SP|GP) per Day)\)$', name)
        e = {'id': m.group(1).lower(), 'name': m.group(1),
             'cost_cp_per_day': 0 if m.group(2) == 'Free' else money_cp(f'{m.group(3)} {m.group(4)}'),
             'description': render(body)}
        life.append(e)
    eco['lifestyles'] = life
    eco['lifestyle_rules'] = render(sections(secs['Lifestyle Expenses'], 3)[0][1])
    food = next(x[1] for x in secs['Food, Drink, and Lodging'] if x[0] == 'table')
    services = []
    parent = None
    for r in food['rows']:
        if not r[1]:
            parent = r[0]
            continue
        if parent and r[0] in ('Squalid', 'Poor', 'Modest', 'Comfortable', 'Wealthy', 'Aristocratic', 'Common',
                               'Fine'):
            if parent == 'Inn Stay per Day':
                e = {'id': f'inn-stay-{r[0].lower()}', 'name': f'Inn stay ({r[0]})', 'category': 'lodging',
                     'tier': r[0].lower(), 'unit': 'night'}
            elif parent == 'Meal':
                e = {'id': f'meal-{r[0].lower()}', 'name': f'Meal ({r[0]})', 'category': 'food', 'tier': r[0].lower(),
                     'unit': 'meal'}
            else:
                e = {'id': f'wine-{r[0].lower()}', 'name': f'Wine ({r[0]}, bottle)', 'category': 'drink',
                     'tier': r[0].lower(), 'unit': 'bottle'}
        else:
            parent = None
            nm = r[0]
            unit = re.search(r'\((\w+)\)', nm)
            e = {'id': slug(nm), 'name': nm, 'category': 'drink' if nm.startswith('Ale') else 'food',
                 'unit': unit.group(1) if unit else None}
        cost_fields(e, r[1])
        services.append(e)
    eco['food_drink_lodging'] = services
    eco['food_drink_lodging_rules'] = render([x for x in secs['Food, Drink, and Lodging'] if x[0] == 'p'])
    hire = next(x[1] for x in secs['Hirelings'] if x[0] == 'table')
    eco['hirelings'] = []
    for r in hire['rows']:
        m = re.match(r'^(\d+) (CP|SP|GP) per (day|mile)$', r[1])
        e = {'id': slug(r[0]), 'name': r[0], 'cost_cp': money_cp(f'{m.group(1)} {m.group(2)}'), 'unit': m.group(3)}
        eco['hirelings'].append(e)
    eco['hireling_rules'] = render([x for x in secs['Hirelings'] if x[0] == 'p'])
    sc = next(x[1] for x in secs['Spellcasting'] if x[0] == 'table')
    eco['spellcasting_services'] = [{'spell_level': r[0], 'availability': r[1], 'cost_cp': money_cp(r[2])}
                                    for r in sc['rows']]
    eco['spellcasting_service_rules'] = render([x for x in secs['Spellcasting'] if x[0] == 'p'])
    ss = next(x[1] for x in secs['Scribing Spell Scrolls'] if x[0] == 'table')
    eco['spell_scroll_scribing'] = [{'spell_level': r[0], 'days': int(r[1].split(' ')[0]), 'cost_cp': money_cp(r[2])}
                                    for r in ss['rows']]
    eco['crafting_rules'] = {
        'nonmagical': render(secs['Crafting Nonmagical Items']),
        'potions_of_healing': render(secs['Brewing Potions of Healing']),
        'spell_scrolls': render([x for x in secs['Scribing Spell Scrolls'] if x[0] != 'table']),
    }
    eco['magic_item_rules'] = render(secs['Magic Items'])
    # Wage classes for the affordability guard (docs/requirements.md "Shops and economy"): what a day's
    # work earns, from the Hirelings table.
    by = {h['id']: h for h in eco['hirelings']}
    eco['wages'] = [
        {'id': 'unskilled', 'name': 'Unskilled worker (untrained hireling)', 'cp_per_day': by['untrained-hireling']['cost_cp']},
        {'id': 'skilled', 'name': 'Skilled worker (skilled hireling)', 'cp_per_day': by['skilled-hireling']['cost_cp']},
    ]
    return eco


def rules_text(chapter):
    secs = dict(sections(chapter, 2)[1:])
    w = dict(sections(secs['Weapons'], 3)[1:])
    out = {}
    out['weapon_rules'] = render([x for x in sections(secs['Weapons'], 3)[0][1] if x[0] != 'table'])
    out['weapon_properties'] = [{'name': n, 'description': render(b)} for n, b in sections(w['Properties'], 4)[1:]]
    out['mastery_properties'] = [{'name': n, 'description': render([x for x in b if x[0] != 'table'])}
                                 for n, b in sections(w['Mastery Properties'], 4)[1:]]
    out['armor_rules'] = render([x for x in secs['Armor'] if x[0] != 'table'])
    out['tool_rules'] = render(sections(secs['Tools'], 3)[1][1]) if sections(secs['Tools'], 3)[1:] else ''
    out['mount_rules'] = render([x for x in secs['Mounts and Vehicles'] if x[0] != 'table'])
    return out


def parse(chapter):
    secs = dict(sections(chapter, 2)[1:])
    tables = {x[1]['caption']: x[1] for x in chapter if x[0] == 'table' and x[1].get('caption')}
    items = []
    items += weapons(tables['Weapons'])
    items += armor(tables['Armor'])
    items += tools(secs['Tools'])
    items += gear(secs['Adventuring Gear'])
    items += mounts(secs['Mounts and Vehicles'])
    for d in items:
        d.setdefault('legality', 'legal')
        d['shop_types'] = shop_types(d)
    return {'items': items, 'rules': rules_text(chapter)}, economy(chapter)


def label(text):
    return split_label(text)[0]


def table(t):
    return table_data(t)
