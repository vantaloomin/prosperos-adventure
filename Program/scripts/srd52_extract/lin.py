# ruff: noqa: C901
"""Linearize the SRD PDF into lines with style info, in content-stream order."""
import json
import sys

import pymupdf


def style(font, size):
    b = 'Bold' in font or 'SemiBold' in font
    i = 'Italic' in font
    fam = font.split('-')[0]
    return fam, b, i


MID = 297
TABLE_SIZES = (10.5, 9.2, 9.5, 9.8, 8.0, 6.0, 6.8)


def reorder(lines):
    """Put each page's blocks in reading order: bands split by full-width blocks; in a band, the left
    column top to bottom, then the right column. The PDF's own stream order floats stat blocks and
    column tops out of place."""
    out = []
    pages = {}
    for ln in lines:
        pages.setdefault(ln['p'], {}).setdefault(ln['b'], []).append(ln)
    for p in sorted(pages):
        blocks = []
        for b, lns in pages[p].items():
            x0 = min(q['x'] for q in lns)
            x1 = max(q['x1'] for q in lns)
            y0 = min(q['y'] for q in lns)
            col = 2 if (x0 < MID - 10 and x1 > MID + 25) else (0 if x0 < MID else 1)
            blocks.append({'b': b, 'lns': lns, 'y': y0, 'col': col})
        # a run of stream-consecutive table blocks (caption, header, rows) moves as one unit, so tables set
        # side by side in a column keep their own order
        by_b = sorted(blocks, key=lambda bl: bl['b'])
        units = []
        for bl in by_b:
            tab = all(sp['f'].startswith('GillSans') and sp['s'] in TABLE_SIZES
                      for ln in bl['lns'] for sp in ln['spans'] if sp['t'].strip())
            y1 = max(ln['y'] for ln in bl['lns'])
            x0 = min(ln['x'] for ln in bl['lns'])
            x1 = max(ln['x1'] for ln in bl['lns'])
            u = units[-1] if units else None
            if tab and u and u['tab'] and (u['col'] == bl['col'] or u['y'] - 5 <= bl['y'] <= u['y1'] + 20):
                u['lns'] += bl['lns']
                u['y'] = min(u['y'], bl['y'])
                u['y1'] = max(u['y1'], y1)
                u['x0'] = min(u['x0'], x0)
                u['x1'] = max(u['x1'], x1)
                if u['col'] != bl['col']:
                    u['col'] = 2 if (u['x0'] < MID - 10 and u['x1'] > MID + 25) else bl['col']
            else:
                units.append({'b': bl['b'], 'lns': list(bl['lns']), 'y': bl['y'], 'y1': y1, 'x0': x0, 'x1': x1,
                              'col': bl['col'], 'tab': tab})
        blocks = units
        wide = sorted([bl for bl in blocks if bl['col'] == 2], key=lambda bl: bl['y'])
        cols = [bl for bl in blocks if bl['col'] != 2]
        order = []
        top = -1e9
        for w in wide + [None]:
            bottom = w['y'] if w else 1e9
            band = [bl for bl in cols if top <= bl['y'] < bottom]
            order += sorted(band, key=lambda bl: (bl['col'], bl['y']))
            if w:
                order.append(w)
            top = bottom
        for i, bl in enumerate(order):
            for ln in bl['lns']:
                ln['b0'] = ln['b']
                ln['b'] = i
                out.append(ln)
    return out


def main(pdf, out):
    doc = pymupdf.open(pdf)
    lines = []
    for pno, page in enumerate(doc, 1):
        d = page.get_text('dict', flags=pymupdf.TEXT_PRESERVE_WHITESPACE | pymupdf.TEXT_MEDIABOX_CLIP)
        for b in d['blocks']:
            for line in b.get('lines', []):
                spans = []
                for s in line['spans']:
                    if not s['text']:
                        continue
                    fam, bold, it = style(s['font'], s['size'])
                    spans.append({'t': s['text'], 'f': s['font'], 's': round(s['size'], 1), 'b': bold, 'i': it,
                                  'x': round(s['bbox'][0], 1), 'y': round(s['origin'][1] - s['size'], 1), 'x1': round(s['bbox'][2], 1)})
                if not spans or not ''.join(x['t'] for x in spans).strip():
                    continue
                # page furniture
                if spans[0]['f'] == 'GillSans' and spans[0]['s'] == 11.0 and spans[0]['t'].startswith('System Reference'):
                    continue
                if spans[0]['f'] == 'GillSans-SemiBold' and spans[0]['s'] == 11.0 and spans[0]['t'].strip().isdigit():
                    continue
                lines.append({'p': pno, 'b': b['number'], 'x': spans[0]['x'], 'y': spans[0]['y'],
                              'x1': max(x['x1'] for x in spans), 'spans': spans})
    lines = reorder(lines)
    json.dump(lines, open(out, 'w'))
    print(len(lines))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
