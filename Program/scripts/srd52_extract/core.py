# ruff: noqa: C901
"""Turn the linearized SRD lines into a document of items: headings, paragraphs, tables, stat-block lines."""
import json
import re
from collections import Counter

HEAD = {('GillSans-SemiBold', 26.0): 1, ('GillSans-SemiBold', 18.0): 2, ('GillSans-SemiBold', 14.0): 3,
        ('GillSans-SemiBold', 14.8): 3, ('GillSans-SemiBold', 12.0): 4, ('GillSans-SemiBold-SC700', 12.0): 4,
        ('GillSans', 12.0): 5, ('GillSans-Bold-SC700', 11.0): 6}
CAPTION = {('GillSans-SemiBold', 10.5)}
TH = {('GillSans-SemiBold', 9.2), ('GillSans-Bold', 9.8)}
TD_FONTS = {'GillSans', 'GillSans-Italic', 'GillSans-SemiBold', 'GillSans-Bold', 'GillSans-SemiBold-SC700',
            'GillSans-BoldItalic'}
TD_SIZES = {9.5, 9.8, 6.0, 6.8, 9.2}


def clean(t):
    return t.replace('\xa0', ' ').replace('­', '').replace('ﬁ', 'fi').replace('ﬂ', 'fl')


def key(span):
    return (span['f'], span['s'])


def first(line):
    for s in line['spans']:
        if s['t'].strip():
            return s
    return line['spans'][0]


def plain(line):
    return clean(''.join(s['t'] for s in line['spans']))


def kind(line):
    s = first(line)
    k = key(s)
    if k in HEAD:
        return 'h'
    if k in CAPTION:
        return 'cap'
    if s['f'].startswith('Optima') and s['s'] == 9.0:
        return 'sbh'  # stat block header lines (type line, AC, HP, ...)
    if s['f'].startswith('GillSans') and s['s'] == 6.0:
        return 'td'
    spans = [x for x in line['spans'] if x['t'].strip()]
    all_bold = all(x['b'] for x in spans)
    if k in TH or (k == ('GillSans-SemiBold', 9.5) and all_bold and ':' not in plain(line)):
        return 'th'
    if s['f'] in ('GillSans-SemiBold', 'GillSans-Bold') and s['s'] in (9.5, 10.0) and clean(s['t']).strip().endswith(':'):
        return 'field'
    if s['f'] == 'Cambria-Bold' and s['s'] == 9.5 and clean(s['t']).strip().endswith(':'):
        return 'field'
    if s['f'] in TD_FONTS and s['s'] in TD_SIZES:
        return 'td'
    if s['f'] == 'GillSans' and s['s'] == 8.0:
        return 'note'
    if s['f'].startswith('GillSans') and s['s'] == 9.0:
        return 'side'
    if s['f'].startswith('Optima'):
        return 'sbody'
    return 'body'


# ---------------------------------------------------------------- dehyphenation

WORD = re.compile(r"[A-Za-z][A-Za-z’'-]*[A-Za-z]")
_words = None


def words(lines=None):
    global _words
    if _words is None:
        c = Counter()
        for line in lines:
            t = plain(line)
            toks = t.split()
            # skip last token (may be a hyphen fragment)
            for tok in toks[:-1] if t.rstrip().endswith('-') else toks:
                for w in WORD.findall(tok):
                    c[w.lower()] += 1
        _words = c
    return _words


def join(a, b):
    """Join two text lines, undoing typesetter hyphenation."""
    if not a:
        return b.lstrip()
    if not b:
        return a
    ar = a.rstrip(' ')
    mk = re.search(r'[A-Za-z’\']-(\*{1,2})$', ar)
    if mk and b.lstrip().startswith(mk.group(1)) and not b.lstrip().startswith(mk.group(1) + '*'):
        marks = mk.group(1)
        return join(ar[:-len(marks)], b.lstrip()[len(marks):])
    if ar.endswith('-') and not ar.endswith(' -') and not ar.endswith('--'):
        m = re.search(r"([A-Za-z’']+)-$", ar)
        n = re.match(r"\**([A-Za-z’']+)", b.lstrip())
        if m and n:
            left, right = m.group(1), n.group(1)
            w = words()
            hy = w[(left + '-' + right).lower()]
            joined = w[(left + right).lower()]
            if right[0].isupper() and not left.isupper():
                return ar + b.lstrip()
            if hy > joined:
                return ar + b.lstrip()
            return ar[:-1] + b.lstrip()
        if re.search(r'\d-$', ar):
            return ar + b.lstrip()
        return ar + b.lstrip()
    if ar.endswith('—') or ar.endswith('/'):
        return ar + b.lstrip()
    return ar + ' ' + b.lstrip()


# ---------------------------------------------------------------- inline markup

def styled(line, skip_tab=True):
    """Markdown-ish text of a line: **bold**, *italic*."""
    out = []
    for s in line['spans']:
        t = clean(s['t']).replace('\t', ' ')
        if not t:
            continue
        mark = '**' if s['b'] else ('*' if s['i'] else '')
        if out and out[-1][0] == mark:
            out[-1][1] += t
        else:
            out.append([mark, t])
    res = ''
    for mark, t in out:
        if not mark or not t.strip():
            res += t
            continue
        lead = t[:len(t) - len(t.lstrip())]
        trail = t[len(t.rstrip()):]
        res += lead + mark + t.strip() + mark + trail
    res = re.sub(r'^\s+', '', res)
    return res


def starts_label(line):
    """The line opens with a bold run label ending in . or : (an inline heading)."""
    spans = [s for s in line['spans'] if s['t'].strip()]
    if not spans or not spans[0]['b']:
        return False
    lab = ''
    for s in spans:
        if not s['b']:
            break
        lab += s['t']
    lab = clean(lab).strip()
    return lab.endswith('.') or lab.endswith(':') or lab.endswith('.)') or re.match(r'^\d+:', lab) is not None


def ends_bold(line):
    spans = [x for x in line['spans'] if x['t'].strip()]
    return bool(spans) and spans[-1]['b'] and not clean(spans[-1]['t']).strip().endswith(('.', ':'))


def starts_new(line):
    t = clean(line['spans'][0]['t'])
    return t.startswith('\t') or t.lstrip().startswith('•') or starts_label(line)


# ---------------------------------------------------------------- tables

def cells(lines):
    """Split table lines into cells: runs of spans with small x gaps."""
    out = []
    for line in lines:
        cur = None
        for s in line['spans']:
            t = clean(s['t'])
            if not t.strip():
                if cur is not None:
                    cur['t'] += ' '
                continue
            th = (s['f'], s['s']) in TH or (s['f'] == 'GillSans-SemiBold' and s['s'] <= 9.5)
            if cur is not None and s['x'] - cur['x1'] < 4 and '\t' not in t:
                cur['t'] += t
                cur['x1'] = s['x1']
            else:
                if cur is not None:
                    out.append(cur)
                cur = {'t': t.replace('\t', ' '), 'x': s['x'], 'x1': s['x1'], 'y': s['y'], 'p': line['p'],
                       'th': th and line is not None and kind(line) == 'th'}
        if cur is not None:
            out.append(cur)
    for c in out:
        c['t'] = re.sub(r'\s+', ' ', c['t']).strip()
    return [c for c in out if c['t']]


def group_rows(cs, tol=4):
    rows = []
    for c in cs:
        if rows and rows[-1][0]['p'] == c['p'] and abs(rows[-1][0]['y'] - c['y']) <= tol:
            rows[-1].append(c)
        else:
            rows.append([c])
    return rows


def header_columns(hcells):
    """Merge stacked header cells into columns by x overlap; drop dash group headers."""
    hcells = [c for c in hcells if not c['t'].startswith('—') and not c['t'].startswith('–—')]
    cols = []
    for c in sorted(hcells, key=lambda c: c['y']):
        for col in cols:
            if c['x'] < col['x1'] - 1 and c['x1'] > col['x'] + 1:
                col['t'] = (col['t'] + ' ' + c['t']).strip()
                col['x'] = min(col['x'], c['x'])
                col['x1'] = max(col['x1'], c['x1'])
                break
        else:
            cols.append(dict(c))
    cols.sort(key=lambda c: c['x'])
    for c in cols:
        c['t'] = re.sub(r'\s+', ' ', c['t']).strip()
    return cols


def assign(cols, c):
    for i, col in enumerate(cols):
        if abs(col['x'] - c['x']) <= 3:
            return i
    over = [(min(col['x1'], c['x1']) - max(col['x'], c['x']), i) for i, col in enumerate(cols)]
    over = [o for o in over if o[0] > 0]
    if over:
        return max(over)[1]
    center = (c['x'] + c['x1']) / 2
    return min(range(len(cols)), key=lambda i: abs((cols[i]['x'] + cols[i]['x1']) / 2 - center))


def build_table(lines, caption=None):
    cs = cells(lines)
    head = [c for c in cs if c['th']]
    body = [c for c in cs if not c['th']]
    # header cells are those before the first body row on the same page (stacked headers)
    if head:
        first_body_y = body[0]['y'] if body else 1e9
        hdr = [c for c in head if c['p'] == head[0]['p'] and c['y'] < first_body_y - 2]
        label_cells = [c for c in head if c not in hdr]
    else:
        hdr, label_cells = [], []
    cols = header_columns(hdr) if hdr else None
    rest = sorted(body + label_cells, key=lambda c: (c['p'], c['y'], c['x']))
    # keep the stream order of pages; within a page sort by y then x
    rows = group_rows(rest)
    if not cols:
        widest = max(rows, key=len) if rows else []
        cols = [dict(c) for c in sorted(widest, key=lambda c: c['x'])]
    out = []
    for r in rows:
        vals = [''] * len(cols)
        for c in sorted(r, key=lambda c: c['x']):
            i = assign(cols, c)
            vals[i] = join(vals[i], c['t']) if vals[i] else c['t']
        lone = vals[0] and not any(vals[1:]) and vals[0][:1].islower()
        if out and lone and sum(1 for v in out[-1] if v) > 1:
            out[-1][0] = join(out[-1][0], vals[0])
        elif out and not vals[0] and any(vals):
            prev = out[-1]
            for i, v in enumerate(vals):
                if v:
                    prev[i] = join(prev[i], v) if prev[i] else v
        else:
            out.append(vals)
    names = [c['t'] for c in cols] if hdr else None
    if names and len(names) % 2 == 0 and names[:len(names) // 2] == names[len(names) // 2:]:
        h = len(names) // 2
        left = [r[:h] for r in out]
        right = [r[h:] for r in out]
        out = [r for r in left + right if any(r)]
        names = names[:h]
    return {'caption': caption, 'columns': names, 'rows': out}


def merge_marks(text):
    text = re.sub(r'\*\*([^*]+)\*\* \*\*([^*]+)\*\*', r'**\1 \2**', text)
    text = re.sub(r'(?<!\*)\*([^*]+)\* \*([^*]+)\*(?!\*)', r'*\1 \2*', text)
    return text


# ---------------------------------------------------------------- items

def items(lines):
    """Group lines into items: ('h', level, text, line), ('p', text), ('table', table), ('field', label, value),
    ('sbh', text), ('note', text)."""
    res = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        k = kind(line)
        if k == 'h':
            lvl = HEAD[key(first(line))]
            text = plain(line)
            j = i + 1
            while j < n and kind(lines[j]) == 'h' and lines[j]['p'] == line['p'] \
                    and (lvl <= 2 or lines[j].get('b0') == line.get('b0')) \
                    and HEAD[key(first(lines[j]))] == lvl and (text.endswith(' ') or text.endswith('-')):
                text = join(text, plain(lines[j]))
                j += 1
            res.append(('h', lvl, re.sub(r'\s+', ' ', text).strip(), line))
            i = j
            continue
        if k in ('cap', 'th', 'td'):
            cap = None
            if k == 'cap':
                cap = plain(line).strip()
                i += 1
            j = i
            seen_td = False
            while j < n and kind(lines[j]) in ('th', 'td'):
                if kind(lines[j]) == 'th' and seen_td and j > i and (
                        lines[j]['y'] < lines[j - 1]['y'] - 5 or lines[j]['p'] != lines[j - 1]['p']):
                    break
                seen_td = seen_td or kind(lines[j]) == 'td'
                j += 1
            end = j
            notes = []
            while j < n and kind(lines[j]) == 'note':
                notes.append(plain(lines[j]))
                j += 1
            tbl = build_table(lines[i:end], cap) if end > i else {'caption': cap, 'columns': None, 'rows': []}
            if notes:
                tbl['notes'] = re.sub(r'\s+', ' ', ' '.join(notes)).strip()
            tbl['page'] = line['p']
            res.append(('table', tbl))
            i = j
            continue
        if k == 'field':
            spans = line['spans']
            lab = ''
            val = ''
            for s in spans:
                if s['b'] and not val.strip():
                    lab += clean(s['t'])
                else:
                    val += clean(s['t'])
            j = i + 1
            while j < n and kind(lines[j]) in ('td', 'body') and lines[j]['x'] > line['x'] + 3 \
                    and (first(lines[j])['f'].startswith('GillSans') and first(lines[j])['s'] in (9.5, 10.0)
                         or first(lines[j])['f'] == 'Cambria' and first(lines[j])['s'] == 9.5):
                val = join(val, plain(lines[j]))
                j += 1
            res.append(('field', lab.strip().rstrip(':'), re.sub(r'\s+', ' ', val).strip()))
            i = j
            continue
        if k == 'note':
            res.append(('note', plain(line).strip()))
            i += 1
            continue
        # paragraph text (body or stat block header)
        text = styled(line)
        j = i + 1
        while j < n and kind(lines[j]) == k and not (starts_new(lines[j]) and not ends_bold(lines[j - 1])) and not (
                lines[j]['b'] != lines[j - 1]['b'] and all(sp['i'] or not sp['t'].strip() for ln in lines[i:j]
                                                           for sp in ln['spans'])):
            text = join(text, styled(lines[j]))
            j += 1
        text = merge_marks(re.sub(r'[ \t]+', ' ', text).strip())
        res.append(('sbh' if k == 'sbh' else 'p', text, line))
        i = j
    return mend(res)


def sidebar(line):
    f = first(line)
    return f['f'].startswith('GillSans') and f['s'] == 9.0


def mend(res):
    """Rejoin a paragraph that a table or sidebar interrupted at a page or column break, and a table
    continued under a repeated header."""
    merged = []
    for it in res:
        if it[0] == 'table' and merged and merged[-1][0] == 'table' and not it[1]['caption'] \
                and it[1]['columns'] and it[1]['columns'] == merged[-1][1]['columns']:
            merged[-1][1]['rows'].extend(it[1]['rows'])
            if it[1].get('notes'):
                merged[-1][1]['notes'] = it[1]['notes']
            continue
        merged.append(it)
    res = merged
    out = []
    for it in res:
        if it[0] == 'p' and not starts_new(it[2]) and not it[1][:1].isupper() and len(out) >= 2:
            k = len(out) - 1
            # skip tables, notes and sidebars (a level 6 heading and its GillSans paragraphs)
            while k >= 0 and (out[k][0] in ('table', 'note') or out[k][0] == 'h' and out[k][1] == 6
                              or out[k][0] == 'p' and sidebar(out[k][2]) and not sidebar(it[2])):
                k -= 1
            if k >= 0 and out[k][0] == 'p' and k < len(out) - 1:
                prev = out[k]
                if not prev[1].rstrip().endswith(('.', ':', '!', '?', '”')):
                    out[k] = ('p', merge_marks(join(prev[1], it[1])), prev[2])
                    continue
        out.append(it)
    return out


def load(path):
    lines = json.load(open(path))
    words(lines)
    return lines


def section(lines, start, end=None, level=None):
    """Lines from the heading whose text == start (optionally at a level) up to the next heading == end."""
    out = []
    on = False
    for line in lines:
        if kind(line) == 'h':
            t = re.sub(r'\s+', ' ', plain(line)).strip()
            if not on and t == start and (level is None or HEAD[key(first(line))] == level):
                on = True
            elif on and end is not None and t == end:
                break
        if on:
            out.append(line)
    return out


def pages(lines, lo, hi):
    return [line for line in lines if lo <= line['p'] <= hi]
