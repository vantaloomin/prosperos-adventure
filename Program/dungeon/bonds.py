"""Bonds (requirements "Progression": the Bonds track; "Off-page beats": bonded characters; the party and
relationships panel).

A bond is a tie the character has with someone met (story_bonds), made one of two ways:
- **Earned:** someone who has come to trust them and like them (feelings trust and affection both WARM or more,
  dungeon/feelings.py) is bonded to them from then on.
- **Sworn:** a line that pledges itself to someone there ("I swear to stand by Hesk", "I forge a bond with Ilse")
  binds the character to them, whatever they feel yet.

A bond lasts. Its person can still turn on the character or die (story_fates, dungeon/beats.py); the bond then shows
as broken or lost. The Bonds track is how many living, unbroken bonds the character has, in words (or the count
while the dice are shown). Life Cards that name {bond} come into play once there is one (dungeon/happenings.py),
and the narrator is told who is bonded to the character.

Bonds are game state, branched with the story (story_bonds is in dungeon/timeline.py SAVED).
"""
import re

from dungeon import sworn as vows
from dungeon.database import many, optional

WARM = 3
SWEAR = re.compile(r"\b(swear\w*|vow\w*|pledg\w*|promis\w*|forg\w* a bond|bind\w* myself|sworn)\b.{0,40}?\b(to )?"
                   r"(stand by|stand with|protect|look after|watch over|be there for|never abandon|never leave|"
                   r"(a )?bond with|myself to|fight for|always help)\b", re.I)
# Fates that end what a bond can do: the person is dead, or turned against the character.
LOST = {'dead': 'lost', 'turned': 'broken'}
WORDS = ((0, 'no one to call on'), (1, 'one true bond'), (2, 'a few who would stand by them'),
         (4, 'well bonded, with friends in many places'))


def forge(connection, key: str, name: str, how: str, since: str) -> bool:
    """A bond with someone; False when there already is one."""
    if optional(connection, 'SELECT 1 FROM story_bonds WHERE key=?', (key,)):
        return False
    connection.execute('INSERT INTO story_bonds (key, name, how, since) VALUES (?, ?, ?, ?)', (key, name, how, since))
    vows.forge_bond(connection, name)
    return True


def earned(connection, key: str):
    """Called when feelings move: someone who trusts and likes the character warmly enough is bonded to them."""
    row = optional(connection, 'SELECT key, name, trust, affection, last_met_at FROM story_people WHERE key=?', (key,))
    if row and (row['trust'] or 0) >= WARM and (row['affection'] or 0) >= WARM:
        forge(connection, row['key'], row['name'], 'earned', row['last_met_at'])


def sworn(connection, text: str, people: list[dict], now: str) -> list[str]:
    """A line that pledges the character to someone in the scene: the bond, and the line for the narrator."""
    from dungeon import combat
    if not SWEAR.search(text):
        return []
    person = next((person for person in people if combat.aimed(person, text)), None)
    if person is None:
        return []
    name = person['sheet']['full']
    if not forge(connection, person['sheet']['key'], name, 'sworn', now):
        return []
    tracked = vows.bonds_line(connection)
    return [f"The player's character binds themselves to {name}: a bond from now on, kept by the game."] + \
        ([tracked] if tracked else [])


def bonds(connection) -> list[dict]:
    """Every bond, oldest first, with its state: 'whole', or 'broken' (turned) or 'lost' (dead)."""
    fates = {row['key']: row['state'] for row in many(connection, 'SELECT key, state FROM story_fates')}
    return [row | {'state': LOST.get(fates.get(row['key'], ''), 'whole')}
            for row in many(connection, 'SELECT * FROM story_bonds ORDER BY since, name')]


def whole(connection) -> list[dict]:
    return [row for row in bonds(connection) if row['state'] == 'whole']


def word(count: int) -> str:
    return next(said for least, said in reversed(WORDS) if count >= least)


def track(connection, shown: bool) -> dict:
    """The Bonds track for the sheet: in words, and the count while the dice are shown."""
    found = bonds(connection)
    count = sum(row['state'] == 'whole' for row in found)
    return {'word': word(count), 'bonds': [{'key': row['key'], 'name': row['name'], 'how': row['how'],
                                            'state': row['state']} for row in found]} | \
        ({'count': count} if shown else {})


def prompt_text(lines: list[str]) -> str:
    return '## A bond (decided by the game)\n' + '\n'.join(f'- {line}' for line in lines) if lines else ''
