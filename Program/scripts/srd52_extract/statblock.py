# ruff: noqa: C901
"""Parse a 2024-style stat block from document items."""
import re

from common import ABBR, CONDITIONS, DAMAGE_TYPES, damage_list, num, split_label, unmark

SIZES = ('Tiny', 'Small', 'Medium', 'Large', 'Huge', 'Gargantuan')
FIELDS = ('AC', 'Initiative', 'HP', 'Speed', 'Skills', 'Resistances', 'Vulnerabilities', 'Immunities', 'Senses',
          'Languages', 'CR', 'Gear')
SECTIONS = {'Traits': 'traits', 'Actions': 'actions', 'Bonus Actions': 'bonus_actions', 'Reactions': 'reactions',
            'Legendary Actions': 'legendary_actions'}
CR_XP = {}


def type_line(s):
    s = s.strip().strip('*').strip()
    m = re.match(r'^(.*?),\s*([^,]+)$', s)
    head, align = (m.group(1), m.group(2)) if m else (s, None)
    sizes = []
    words = head.split(' ')
    i = 0
    while i < len(words) and (words[i] in SIZES or words[i] in ('or', 'Smaller')):
        if words[i] in SIZES:
            sizes.append(words[i])
        i += 1
    rest = ' '.join(words[i:])
    tags = None
    tm = re.match(r'^(.*?)\s*\((.+)\)$', rest)
    if tm:
        rest, tags = tm.group(1), tm.group(2)
    return {'size': sizes, 'size_text': ' '.join(words[:i]), 'type': rest, 'tags': tags, 'alignment': align}


def speed(s):
    out = {}
    for part in [p.strip() for p in s.split(',')]:
        m = re.match(r'^(?:(Burrow|Climb|Fly|Swim)\s+)?(\d+)\s*ft\.(.*)$', part)
        if m:
            k = (m.group(1) or 'walk').lower()
            out[k] = int(m.group(2))
            if 'hover' in m.group(3):
                out['hover'] = True
    return out


def listing(s):
    return [x.strip() for x in re.split(r',\s*(?:and\s+)?', s) if x.strip()]


def immunities(s):
    dmg, cond = [], []
    parts = s.split(';')
    for i, part in enumerate(parts):
        for tok in listing(part):
            base = tok.split(' ')[0]
            if base in CONDITIONS:
                cond.append(tok)
            elif base in DAMAGE_TYPES or i == 0 and len(parts) > 1:
                dmg.append(tok)
            else:
                (cond if base in CONDITIONS else dmg).append(tok)
    return dmg, cond


def cr(s):
    m = re.match(r'^(\d+(?:/\d+)?)\s*\((.*)\)', s)
    if not m:
        return {'cr': s}
    val = m.group(1)
    crn = eval(val) if '/' in val else int(val)  # noqa: S307 (digits only)
    d = {'cr': val, 'cr_value': crn}
    inner = m.group(2)
    xm = re.search(r'XP ([\d,]+)(?: or ([\d,]+))?(?:, or ([\d,]+) in lair)?', inner) or \
        re.search(r'([\d,]+) XP(?: or ([\d,]+))?(?:, or ([\d,]+) in lair)?', inner)
    if xm:
        d['xp'] = int(xm.group(1).replace(',', ''))
        if xm.group(2):
            d['xp_alt'] = int(xm.group(2).replace(',', ''))
        if xm.group(3):
            d['xp_lair'] = int(xm.group(3).replace(',', ''))
    pm = re.search(r'PB ([+−-]\d+)', inner)
    if pm:
        d['proficiency_bonus'] = num(pm.group(1))
    return d


def senses(s):
    out = {}
    for part in re.split(r'[;,]\s*', s):
        m = re.match(r'^(Blindsight|Darkvision|Tremorsense|Truesight)\s+(\d+)\s*ft\.(.*)$', part.strip())
        if m:
            out[m.group(1).lower()] = int(m.group(2))
            if m.group(3).strip():
                out[m.group(1).lower() + '_note'] = m.group(3).strip()
        m = re.match(r'^Passive Perception (\d+)', part.strip())
        if m:
            out['passive_perception'] = int(m.group(1))
    return out


def usage(name):
    """'Acid Breath (Recharge 5–6)' -> ('Acid Breath', {...})."""
    m = re.match(r'^(.*?)\s*\((.+)\)$', name)
    if not m:
        return name, None
    base, inner = m.group(1), m.group(2)
    u = {'text': inner}
    rm = re.search(r'Recharge (\d)(?:[–-](\d))?', inner)
    if rm:
        u['recharge'] = [int(rm.group(1)), int(rm.group(2) or 6)]
    dm = re.search(r'(\d+)/Day', inner)
    if dm:
        u['per_day'] = int(dm.group(1))
    if 'Recharges after a Short or Long Rest' in inner:
        u['recharge_rest'] = 'short'
    elif 'Recharges after a Long Rest' in inner:
        u['recharge_rest'] = 'long'
    if not (rm or dm or 'Recharge' in inner or 'Costs' in inner):
        return name, None
    cm = re.search(r'Costs (\d+) Actions', inner)
    if cm:
        u['cost'] = int(cm.group(1))
    return base, u


def mechanics(text):
    """Attack and save details from an action's text."""
    t = unmark(text)
    out = {}
    m = re.search(r'(Melee or Ranged|Melee|Ranged) Attack Roll:\s*([+−-]\d+)(.*?)Hit:', t, re.S)
    if m:
        a = {'kind': m.group(1).lower().replace(' or ', '_or_'), 'bonus': num(m.group(2))}
        rest = m.group(3) or ''
        cm = re.match(r'^\s*\(([^)]*)\)', rest)
        if cm:
            a['bonus_note'] = cm.group(1)
        rm = re.search(r'reach (\d+) ft', rest)
        if rm:
            a['reach'] = int(rm.group(1))
        gm = re.search(r'range (\d+)(?:/(\d+))? ft', rest)
        if gm:
            a['range'] = int(gm.group(1))
            if gm.group(2):
                a['range_long'] = int(gm.group(2))
        hm = re.search(r'Hit:\s*(.*?)(?=(?:Miss:|Hit or Miss:|$))', t[m.end() - 4:], re.S)
        if hm:
            a['hit'] = hm.group(1).strip()
            a['damage'] = damage_list(hm.group(1))
        out['attack'] = a
    sm = re.search(r'(Strength|Dexterity|Constitution|Intelligence|Wisdom|Charisma) Saving Throw:\s*DC (\d+)'
                   r'(?:,\s*([^.]*))?', t)
    if sm:
        s = {'ability': sm.group(1)[:3].lower(), 'dc': int(sm.group(2))}
        if sm.group(3):
            s['targets'] = sm.group(3).strip()
        fm = re.search(r'Failure:?\s*(.*?)(?=(?:Success:|Failure or Success:|First Failure:|Second Failure:|$))',
                       t[sm.end():], re.S)
        if fm:
            s['failure'] = fm.group(1).strip()
            s['damage'] = damage_list(fm.group(1))
        um = re.search(r'(?<!or )Success:\s*(.*?)(?=(?:Failure or Success:|$))', t[sm.end():], re.S)
        if um:
            s['success'] = um.group(1).strip()
        out['save'] = s
    return out


def spellcasting(entry, extra):
    """Spell lists under a Spellcasting entry: {'At Will': [...], '1/Day Each': [...]}"""
    lists = {}
    for line in extra:
        lab, rest = split_label(line)
        if lab is None:
            continue
        lab = lab.rstrip(':')
        names = re.findall(r'\*([^*]+)\*(?:\s*\(([^)]*)\))?', rest)
        lists[lab] = [{'spell': n, **({'note': note} if note else {})} for n, note in names]
    m = re.search(r'spell save DC (\d+)', entry)
    a = re.search(r'([+−-]\d+) to hit with spell attacks', entry)
    ab = re.search(r'using (\w+) as the spellcasting ability', entry)
    d = {'lists': lists}
    if m:
        d['save_dc'] = int(m.group(1))
    if a:
        d['attack_bonus'] = num(a.group(1))
    if ab:
        d['ability'] = ab.group(1)[:3].lower()
    return d


def entries(its):
    out = []
    for it in its:
        if it[0] not in ('p', 'sbh', 'table'):
            continue
        if it[0] == 'table':
            if out:
                from common import table_md
                out[-1]['text'] += '\n\n' + table_md(it[1])
            continue
        lab, rest = split_label(it[1])
        if lab is not None and not lab.endswith(':') and out is not None and not (
                out and out[-1]['name'] == 'Spellcasting' and lab.endswith(':')):
            name, use = usage(lab)
            e = {'name': name, 'text': rest}
            if use:
                e['usage'] = use
            out.append(e)
        elif out:
            out[-1].setdefault('_extra', []).append(it[1])
            out[-1]['text'] += '\n\n' + it[1]
        else:
            out.append({'name': None, 'text': it[1]})
    for e in out:
        extra = e.pop('_extra', [])
        if e['name'] == 'Spellcasting' or e['name'] and e['name'].startswith('Spellcasting'):
            e['spellcasting'] = spellcasting(e['text'].split('\n\n')[0], extra)
        e.update(mechanics(e['text']))
    return out


def parse(name, its):
    sb = {'name': name}
    head = []
    tail = []
    abil_rows = []
    sections = {}
    cur = None
    seen_table = False
    for it in its:
        if it[0] == 'h' and it[1] == 5:
            cur = SECTIONS.get(it[2], it[2].lower().replace(' ', '_'))
            sections.setdefault(cur, [])
            continue
        if cur is None:
            if it[0] == 'table' and not seen_table:
                abil_rows = it[1]['rows'] + ([it[1]['columns']] if it[1]['columns'] else [])
                seen_table = True
            elif it[0] == 'sbh':
                (tail if seen_table else head).append(it[1])
            elif it[0] == 'p':
                tail.append(it[1])
            continue
        sections[cur].append(it)
    htext = ' '.join(head + tail)
    tm = re.match(r'^\*([^*]+)\*', htext.strip())
    if tm:
        sb.update(type_line(tm.group(1)))
    fields = {}
    parts = re.split(r'\*\*(' + '|'.join(FIELDS) + r')\*\*', htext)
    for i in range(1, len(parts) - 1, 2):
        fields[parts[i]] = unmark(parts[i + 1]).strip()
    if 'AC' in fields:
        m = re.match(r'^(\d+)\s*(.*)$', fields['AC'])
        sb['ac'] = int(m.group(1)) if m else fields['AC']
        if m and m.group(2):
            sb['ac_note'] = m.group(2).strip()
    if 'Initiative' in fields:
        m = re.match(r'^([+−-]\d+)\s*\((\d+)\)', fields['Initiative'])
        if m:
            sb['initiative'] = {'modifier': num(m.group(1)), 'score': int(m.group(2))}
        else:
            sb['initiative'] = {'text': fields['Initiative']}
    if 'HP' in fields:
        m = re.match(r'^(\d+)\s*\(([^)]+)\)$', fields['HP'])
        if m:
            sb['hp'] = {'average': int(m.group(1)), 'formula': m.group(2).replace(' ', '').replace('−', '-')}
        else:
            sb['hp'] = {'text': fields['HP']}
    if 'Speed' in fields:
        sb['speed'] = speed(fields['Speed'])
        sb['speed_text'] = fields['Speed']
    flat = ' '.join(c for r in abil_rows for c in r if c and c not in ('MOD', 'SAVE'))
    flat = re.sub(r'\s+', ' ', flat)
    ab = {}
    for m in re.finditer(r'(Str|Dex|Con|Int|Wis|Cha)\s+(\d+)\s+([+−-]\d+)\s+([+−-]?\d+)', flat):
        ab[ABBR[m.group(1)]] = {'score': int(m.group(2)), 'mod': num(m.group(3)), 'save': num(m.group(4))}
        if not re.match(r'[+−-]', m.group(4)):
            ab[ABBR[m.group(1)]]['_unsigned_save'] = True
    if ab:
        sb['abilities'] = ab
    if 'Skills' in fields:
        sk = {}
        for tok in listing(fields['Skills']):
            m = re.match(r'^(.+?)\s+([+−-]\d+)$', tok)
            if m:
                sk[m.group(1)] = num(m.group(2))
        sb['skills'] = sk
    for k in ('Resistances', 'Vulnerabilities'):
        if k in fields:
            sb[k.lower()] = listing(fields[k].replace(';', ','))
    if 'Immunities' in fields:
        d, c = immunities(fields['Immunities'])
        if d:
            sb['damage_immunities'] = d
        if c:
            sb['condition_immunities'] = c
    if 'Gear' in fields:
        sb['gear'] = listing(fields['Gear'])
    if 'Senses' in fields:
        sb['senses'] = senses(fields['Senses'])
        sb['senses_text'] = fields['Senses']
    if 'Languages' in fields:
        sb['languages'] = fields['Languages']
    if 'CR' in fields:
        sb.update(cr(fields['CR']))
    for key, its2 in sections.items():
        if key == 'legendary_actions':
            intro = [it[1] for it in its2 if it[0] == 'sbh']
            body = [it for it in its2 if it[0] != 'sbh']
            la = {'intro': unmark(' '.join(intro)).strip(), 'actions': entries(body)}
            m = re.search(r'Legendary Action Uses:\s*(\d+)(?:\s*\((\d+) in Lair\))?', la['intro'])
            if m:
                la['uses'] = int(m.group(1))
                if m.group(2):
                    la['uses_lair'] = int(m.group(2))
            sb['legendary_actions'] = la
        else:
            sb[key] = entries(its2)
    return sb
