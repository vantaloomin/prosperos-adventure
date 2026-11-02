# ruff: noqa: C901
"""Shared helpers for the SRD section parsers."""
import re

DAMAGE_TYPES = ('Acid', 'Bludgeoning', 'Cold', 'Fire', 'Force', 'Lightning', 'Necrotic', 'Piercing', 'Poison',
                'Psychic', 'Radiant', 'Slashing', 'Thunder')
CONDITIONS = ('Blinded', 'Charmed', 'Deafened', 'Exhaustion', 'Frightened', 'Grappled', 'Incapacitated',
              'Invisible', 'Paralyzed', 'Petrified', 'Poisoned', 'Prone', 'Restrained', 'Stunned', 'Unconscious')
ABILITIES = ('Strength', 'Dexterity', 'Constitution', 'Intelligence', 'Wisdom', 'Charisma')
ABBR = {'Str': 'str', 'Dex': 'dex', 'Con': 'con', 'Int': 'int', 'Wis': 'wis', 'Cha': 'cha'}
AB_KEY = {a: a[:3].lower() for a in ABILITIES}


def slug(name):
    s = name.lower().replace('’', '').replace("'", '').replace('+', 'plus-')
    s = re.sub(r'[^a-z0-9]+', '-', s).strip('-')
    return s


def table_md(t):
    out = []
    if t.get('caption'):
        out.append(f"**{t['caption']}**")
        out.append('')
    cols = t.get('columns')
    rows = t['rows']
    if not cols and rows:
        cols, rows = rows[0], rows[1:]
    if cols:
        out.append('| ' + ' | '.join(c or ' ' for c in cols) + ' |')
        out.append('|' + '---|' * len(cols))
    for r in rows:
        out.append('| ' + ' | '.join(c.replace('|', '/') for c in r) + ' |')
    if t.get('notes'):
        out.append('')
        out.append(t['notes'])
    return '\n'.join(out)


def table_data(t):
    """A table as {caption, columns, rows, notes} without page info."""
    d = {'caption': t.get('caption'), 'columns': t.get('columns'), 'rows': t['rows']}
    if not d['columns'] and d['rows']:
        d['columns'], d['rows'] = d['rows'][0], d['rows'][1:]
    if t.get('notes'):
        d['notes'] = t['notes']
    return d


def render(its):
    parts = []
    for it in its:
        if it[0] in ('p', 'sbh', 'note'):
            parts.append(it[1])
        elif it[0] == 'table':
            parts.append(table_md(it[1]))
        elif it[0] == 'field':
            parts.append(f'**{it[1]}:** {it[2]}')
        elif it[0] == 'h':
            parts.append(f'**{it[2]}**')
    return '\n\n'.join(parts)


def unmark(s):
    return s.replace('**', '').replace('*', '')


def split_label(text):
    """'**Name.** rest' -> (name, rest); otherwise (None, text)."""
    m = re.match(r'^\*\*(.+?)\*\*\s*(.*)$', text, re.S)
    if not m:
        return None, text
    return m.group(1).strip().rstrip('.').strip(), m.group(2).strip()


def blocks(its, level):
    """Split items into [(heading_text, heading_item, [items])] at headings of the given level."""
    out = []
    cur = None
    for it in its:
        if it[0] == 'h' and it[1] <= level:
            if it[1] == level:
                cur = (it[2], it, [])
                out.append(cur)
            else:
                cur = None
            continue
        if cur is not None:
            cur[2].append(it)
    return out


def money_cp(s):
    """'1,500 GP' -> 150000 copper; None if not a price."""
    if s is None:
        return None
    m = re.match(r'^\s*([\d,]+(?:\.\d+)?)\s*(CP|SP|EP|GP|PP)\b', s.strip())
    if not m:
        return None
    n = float(m.group(1).replace(',', ''))
    mult = {'CP': 1, 'SP': 10, 'EP': 50, 'GP': 100, 'PP': 1000}[m.group(2)]
    return int(round(n * mult))


def weight_lb(s):
    if s is None:
        return None
    s = s.strip()
    if s in ('—', '-', ''):
        return 0
    m = re.match(r'^(\d+)/(\d+)\s*lb', s)
    if m:
        return int(m.group(1)) / int(m.group(2))
    m = re.match(r'^([\d,.]+)\s*lb', s)
    if m:
        return float(m.group(1).replace(',', ''))
    return None


def damage_list(text):
    """All 'NdM[+K] Type damage' and 'N (NdM + K) Type damage' mentions."""
    t = unmark(text)
    out = []
    for m in re.finditer(r'(?:(\d+) \()?(\d+d\d+(?:\s*[+−–-]\s*\d+)?)\)?\s+(' + '|'.join(DAMAGE_TYPES) + r') damage',
                         t):
        d = {'dice': m.group(2).replace(' ', '').replace('−', '-').replace('–', '-'), 'type': m.group(3).lower()}
        if m.group(1):
            d['average'] = int(m.group(1))
        out.append(d)
    for m in re.finditer(r'(?<![\d(+−-])(?<![\d] )\b(\d+) (' + '|'.join(DAMAGE_TYPES) + r') damage', t):
        out.append({'flat': int(m.group(1)), 'type': m.group(2).lower()})
    return out


def num(s):
    s = s.replace('−', '-').replace('–', '-').replace('+', '').replace(',', '').strip()
    try:
        return int(s)
    except ValueError:
        return None


def relocate_tables(groups):
    """Move a captioned table that floated into the wrong entry to the one entry whose text names it.

    groups: list of dicts with 'name' and '_items'."""
    def text_of(g):
        return ' '.join(unmark(it[1]) for it in g['_items'] if it[0] == 'p')
    texts = [text_of(g) for g in groups]
    for g in groups:
        keep = []
        for it in g['_items']:
            cap = it[1].get('caption') if it[0] == 'table' else None
            if cap:
                own = cap in text_of(g) or cap.lower() in g['name'].lower() or g['name'].lower() in cap.lower()
                if not own:
                    owners = [h for h, t in zip(groups, texts) if cap + ' table' in t]
                    if len(owners) == 1 and owners[0] is not g:
                        owners[0]['_items'].append(it)
                        continue
            keep.append(it)
        g['_items'] = keep
