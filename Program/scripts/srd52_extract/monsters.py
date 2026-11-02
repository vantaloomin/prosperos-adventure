# ruff: noqa: C901
"""Monsters A–Z and Animals."""
import statblock
from common import slug

FIXES = []


def parse(its):
    out = []
    cat = group = None
    cur = None
    for it in its:
        if it[0] == 'h' and it[1] <= 3:
            if cur:
                out.append(cur)
                cur = None
            if it[1] == 1:
                cat = 'animal' if it[2] == 'Animals' else 'monster'
                group = None
            elif it[1] == 2:
                group = it[2]
            else:
                cur = {'name': it[2], 'category': cat, 'group': group, '_items': []}
            continue
        if cur:
            cur['_items'].append(it)
    if cur:
        out.append(cur)
    res = []
    for m in out:
        sb = statblock.parse(m['name'], m['_items'])
        for ab in sb.get('abilities', {}).values():
            if ab.pop('_unsigned_save', False) and ab['mod'] < 0 and ab['save'] == -ab['mod']:
                # Source typo (Young White Dragon Int save printed as "2"); a save can't sit above the
                # modifier by more than the proficiency bonus, so the minus sign was lost.
                ab['save'] = ab['mod']
                FIXES.append(f"{m['name']}: saving throw printed without its minus sign; read as {ab['save']}")
        sb = {'id': slug(m['name']), 'category': m['category'], 'group': m['group'] if m['group'] != m['name'] else None,
              **sb}
        res.append(sb)
    return res
