"""Allies in a fight (requirements "Combat": autonomous allies; "NPCs and party": never commanded).

The character's companions (dungeon/party.py) fight beside them, on their own: each round, after the character's
move, each ally still on their feet goes for the foe worst hurt already (code's tactic; they take no orders), rolling
their own skill on the d100 (dungeon/rules/marvel.py roll): FIGHTER for someone whose work is fighting, else
COMMONER. A hit hurts the foe in the campaign's own terms (a wound level, hit points, or Ironsworn harm).

Foes split their blows: each foe still standing turns on an ally instead of the character, one in (allies + 1) of
the time, and that foe's attack lands half the time. An ally who takes HITS_DOWN hits is down and out of the fight,
and the record keeps that they were hurt badly. Allies' state is kept in the fight (state['allies']).
"""
import re

from dungeon import combat5e, combat_brp, combat_iron, party, record
from dungeon.rules import marvel

FIGHTER, COMMONER = 60, 35
FIGHTING = re.compile(r'\b(guard|warden|soldier|sellsword|mercenary|hunter|watch\w*|knight|squire|smith|cutter|'
                      r'woodcutter|brawler|bouncer|sergeant|captain|militia|ranger|duelist|fighter|warrior)\b', re.I)
HITS_DOWN = 2
SUCCESS = ('success_cost', 'success', 'critical_success')
HARM = {'success_cost': 1, 'success': 2, 'critical_success': 3}


def skill(sheet: dict) -> int:
    work = f"{sheet.get('occupation') or ''} {sheet.get('role') or ''}"
    return FIGHTER if FIGHTING.search(work) else COMMONER


def join(connection, state: dict) -> list[dict]:
    """The allies in this fight: the party, each joining the first round they are with the character."""
    allies = state.setdefault('allies', [])
    there = {ally['key'] for ally in allies}
    allies += [{'key': row['key'], 'name': row['name'], 'skill': skill(row['sheet']), 'hits': 0}
               for row in party.members(connection) if row['key'] not in there]
    return allies


def fighting(state: dict) -> list[dict]:
    return [ally for ally in state.get('allies', []) if ally['hits'] < HITS_DOWN]


def hurt(foe: dict, band: str, rng):
    """A foe hit by an ally, in the campaign's terms."""
    if 'npc' in foe:
        combat_iron.inflict(foe, HARM[band])
    elif 'brp' in foe:
        combat_brp.hurt(foe, rng.randint(1, 6) + HARM[band] - 1)
    elif 'hp' in foe:
        combat5e.hurt(foe, rng.randint(1, 6) + HARM[band] - 1)
    else:
        foe['wound'] = min(5, foe['wound'] + HARM[band])


def strike(state: dict, standing, down, rng, lines: list[str]):
    """Each ally on their feet goes for the foe worst hurt already."""
    for ally in fighting(state):
        targets = standing(state)
        if not targets:
            return
        foe = max(targets, key=lambda item: item['wound'])
        band = marvel.roll(ally['skill'], 'normal', rng)['band']
        if band in SUCCESS:
            hurt(foe, band, rng)
            fell = ' and puts them down' if down(foe) else ''
            lines.append(f"{ally['name']}, fighting beside the character, hits {foe['name']}{fell}.")
        else:
            lines.append(f"{ally['name']}, fighting beside the character, goes for {foe['name']} and misses.")


def draw_fire(state: dict, standing, rng, lines: list[str]) -> set[str]:
    """The foes who turn on an ally this round instead of the character; their attacks played. Returns their ids."""
    busy = set()
    for foe in standing(state):
        allies = fighting(state)
        if not allies or rng.random() >= len(allies) / (len(allies) + 1):
            continue
        ally = allies[rng.randrange(len(allies))]
        busy.add(foe['id'])
        if rng.random() < 0.5:
            ally['hits'] += 1
            down = ally['hits'] >= HITS_DOWN
            lines.append(f"{foe['name'].capitalize()} turns on {ally['name']} and hits them"
                         + (": they go down, out of the fight." if down else '.'))
        else:
            lines.append(f"{foe['name'].capitalize()} turns on {ally['name']} and misses.")
    return busy


def aftermath(connection, state: dict, now: str):
    """Allies who went down in a fight that is over are remembered as badly hurt."""
    for ally in state.get('allies', []):
        if ally['hits'] >= HITS_DOWN:
            record.add(connection, 'fact', ally['name'], f"{ally['name']} was badly hurt fighting beside the player's "
                       'character.', now)


def view(state: dict) -> list[dict]:
    return [{'name': ally['name'], 'state': 'down' if ally['hits'] >= HITS_DOWN else 'hurt' if ally['hits'] else
             'unhurt'} for ally in state.get('allies', [])]
