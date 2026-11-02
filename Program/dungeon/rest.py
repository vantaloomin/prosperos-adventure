"""Rest (requirements "Time and travel": resting is risky; "Injuries and recovery"; docs/story.md "Rest").

A line that beds down ("I sleep", "we make camp", "I rest for three days") is a rest, decided before the narrator
writes it:
- **Where decides the danger.** A town (a safe place on the travel map) is safe. Out in the open, each night rolls
  against the region's danger (world/data/travel/<world>.json `regions`), less for each precaution the line takes: a
  watch kept, a hidden camp, an alarm or ward. A dangerous place in town has its own danger, rolled every turn
  (dungeon/quests.py).
- **One night can go wrong.** A night that turns something up draws from the region's camp table: a sight the
  narrator weaves in, or a danger to get past (a Luck roll, a step harder asleep with no watch). One that comes true
  costs that night's rest; one that brings foes starts a fight in the dark, and the rest ends there.
- **Time passes and wounds mend.** The nights pass on the story clock (deadlines land), and each good night counts
  toward the wound's mending (dungeon/combat.py `mend`, gritty Prospero healing). Out in the open each day after the
  first eats one food from the pack; a hungry night does not mend.

Each line's rest is kept with it (story_rests), so telling the turn again changes nothing.
"""
import random
import re
from datetime import datetime, timedelta

from dungeon import combat, quests, story_clock, travel
from dungeon.database import decode, encode, optional

NIGHT_MINUTES = 8 * 60
WAKE_HOUR = 7
MORNING_ENDS = 12
DAY_MINUTES = 24 * 60
CUT_SHORT_MINUTES = 4 * 60
MOST_NIGHTS = 30
RESTING = re.compile(
    r'\b(sleep(s|ing)?(?!\s+with)|go(es|ing)? to bed|turn(s|ing)? in for the night|bed(s|ding)? down|'
    r'(make|makes|making|pitch|pitches|pitching|set up|sets up|setting up) camp|camp(s|ing)? (here|there|out|'
    r'for the night)|rest(s|ing)? (for the night|up|until (morning|dawn)|for (a|an|one|two|three|four|five|six|'
    r'seven|ten|few|couple of|\d+) (day|night|week)s?)|spend(s|ing)? the night|lie up|lay up|recuperate)\b', re.I)
# "for three days", or without the "for": "I sleep three nights at the Wayhouse".
SPAN = re.compile(rf"\b(?:for )?({'|'.join(sorted(story_clock.WORDS, key=len, reverse=True))}|\d+) "
                  r"(day|night|week)s?\b", re.I)
# Precautions, each cutting the odds of a bad night: (name, words, what is left of the odds).
PRECAUTIONS = (
    ('watch', re.compile(r'\b(keep(s|ing)? watch|take (turns|watches)|set(s|ting)? a watch|stand(s|ing)? watch|'
                         r'on watch|sleep(s|ing)? in shifts)\b', re.I), 0.5),
    ('hidden', re.compile(r'\b(hidden|out of sight|off the road|away from the road|no fire|without a fire|'
                          r'cold camp|hide|hides|hiding|concealed)\b', re.I), 0.6),
    ('alarm', re.compile(r'\b(ward(s|ed|ing)?|tripwire|trip line|bells?|alarm|snare line)\b', re.I), 0.7),
)
PRECAUTION_TEXT = {'watch': 'keeping watch', 'hidden': 'the camp hidden', 'alarm': 'an alarm set'}


def resting(text: str) -> bool:
    return bool(RESTING.search(text))


def nights_in(text: str) -> int:
    """How many nights a rest lasts: one unless the line says ("for three days", "for a week")."""
    span = SPAN.search(text)
    if not span:
        return 1
    amount = int(span.group(1)) if span.group(1).isdigit() else story_clock.WORDS[span.group(1).lower()]
    return max(1, min(MOST_NIGHTS, amount * (7 if span.group(2).lower() == 'week' else 1)))


def ground(city_id: str, place_id: str) -> tuple[dict | None, dict | None]:
    """The travel map and the place on it, when the rest is out in the open; (None, None) when it is safe."""
    found = travel.node_at(city_id, place_id)
    if found is None or found[1]['safe']:
        return None, None
    return found


# "I sleep until morning": from the small hours too, the sleep ends with the morning.
UNTIL_MORNING = re.compile(r'\b(?:until|till|til|to)\s+(?:the\s+)?(?:morning|dawn|daybreak|first light|sunrise)\b',
                           re.I)


def plan(city_id: str, place_id: str, text: str, rng=None, connection=None) -> dict:
    return planned(city_id, place_id, text, rng, connection) | ({'morning': True} if UNTIL_MORNING.search(text)
                                                                 else {})


def planned(city_id: str, place_id: str, text: str, rng=None, connection=None) -> dict:
    nights = nights_in(text)
    precautions = [name for name, words, _ in PRECAUTIONS if words.search(text)]
    travel_map, node = ground(city_id, place_id)
    safe = travel_map is None and not quests.danger(city_id, place_id)
    if travel_map is None:
        return {'nights': nights, 'safe': safe, 'precautions': precautions, 'interrupted': None}
    # Out in the wild on a hex crawl, the land the character stopped in decides (dungeon/hexes.py).
    region = travel.region_of(connection, travel_map, node) if connection is not None else node['region']
    odds = travel_map['odds'][travel_map['regions'].get(region, travel_map['regions'][node['region']])['danger']]
    for name, _, left in PRECAUTIONS:
        odds = odds * left if name in precautions else odds
    rng = rng or random.SystemRandom()
    interrupted = None
    for night in range(nights):
        if rng.randint(1, 100) <= round(odds):
            interrupted = {'night': night, 'entry': travel.pick(travel_map['camp'].get(region) or
                                                                travel_map['camp'][node['region']], rng)}
            break
    return {'nights': nights, 'safe': False, 'outside': True, 'precautions': precautions, 'interrupted': interrupted,
            'food': travel_map['food']}


def decide(connection, message_id: str, city_id: str, place_id: str, text: str, rng=None) -> dict | None:
    """The line's rest, planned once, and the roll its night calls for, if any (for the turn's rolls). A journey or
    a fight in progress is no rest."""
    row = optional(connection, 'SELECT plan FROM story_rests WHERE message_id=?', (message_id,))
    if row is None:
        if not resting(text) or optional(connection, 'SELECT 1 FROM story_journeys WHERE message_id=?', (message_id,)):
            return None
        rest = {'fighting': True} if combat.fight(connection) else plan(city_id, place_id, text, rng, connection)
        if combat.captors(connection):
            # A prisoner sleeps under their captors' eyes: no beast comes for them in the night.
            rest['interrupted'] = None
        connection.execute('INSERT INTO story_rests (message_id, plan) VALUES (?, ?)', (message_id, encode(rest)))
    else:
        rest = decode(row['plan'])
    entry = ((rest.get('interrupted') or {}).get('entry')) or {}
    if 'action' not in entry:
        return None
    difficulty = entry['difficulty'] if 'watch' in rest['precautions'] else combat.HARDER[entry['difficulty']]
    return {'action': entry['action'], 'stat': travel.STAT, 'difficulty': difficulty,
            'threat': travel.threat_text(entry['threat'])}


def kept(connection, message_id: str) -> dict | None:
    row = optional(connection, 'SELECT plan, lines FROM story_rests WHERE message_id=?', (message_id,))
    return row and decode(row['plan']) | {'lines': decode(row['lines']) if row['lines'] else None}


def night(rest: dict, rolls: list[dict]) -> tuple[int, int, bool, list[str]]:
    """The nights slept, those of them lost to a bad night, whether a fight cut the rest short, and what happened."""
    nights, interrupted = rest['nights'], rest.get('interrupted')
    if not interrupted:
        # A dangerous place in town has its own danger, rolled this turn: when it comes true, it costs a night.
        return nights, int(any(roll.get('threat') and roll['band'] in quests.BITES for roll in rolls)), False, []
    entry, when = interrupted['entry'], interrupted['night']
    if 'action' not in entry:
        return nights, 0, False, [f"In the night: {entry['text']}"]
    if not travel.bitten(rolls, entry):
        return nights, 0, False, [f"In the night the character manages to {entry['action']}, and sleeps again."]
    lines = [f"In the night: {travel.threat_text(entry['threat'])}"]
    if isinstance(entry['threat'], dict) and entry['threat'].get('foe'):
        return when, 0, True, lines + ['The rest ends here, in the dark, with a fight on its hands.']
    return nights, 1, False, lines


def minutes(nights: int, cut_short: bool, local: datetime | None = None, morning: bool = False) -> int:
    if cut_short:
        return nights * DAY_MINUTES + CUT_SHORT_MINUTES
    return (nights - 1) * DAY_MINUTES + first_night(local, morning)


def first_night(local: datetime | None, morning: bool = False) -> int:
    """A night's sleep runs to the next morning when it starts in the evening or the night (the morning 6 to 15 hours
    off), so bedding down at six wakes at dawn, not at two in the morning; otherwise eight hours. Asked to sleep
    until morning (`morning`), it runs to the next morning from any hour (awake says when it is morning already)."""
    if local is None:
        return NIGHT_MINUTES
    wake = local.replace(hour=WAKE_HOUR, minute=0, second=0, microsecond=0)
    if wake <= local:
        wake += timedelta(days=1)
    gap = int((wake - local).total_seconds() // 60)
    return gap if 6 * 60 <= gap <= 15 * 60 or morning else NIGHT_MINUTES


def awake(local: datetime | None) -> bool:
    """Whether it is morning already (or within the hour of it): sleeping until morning is no sleep at all."""
    if local is None:
        return False
    wake = local.replace(hour=WAKE_HOUR, minute=0, second=0, microsecond=0)
    return WAKE_HOUR <= local.hour < MORNING_ENDS or timedelta(0) <= wake - local < timedelta(hours=1)


def opening(rest: dict) -> str:
    nights = rest['nights']
    how = 'for the night' if nights == 1 else f'for {nights} nights'
    if rest['safe']:
        return f"The player's character rests {how}, somewhere safe."
    where = 'out in the open' if rest.get('outside') else 'in a dangerous place'
    taken = ', '.join(PRECAUTION_TEXT[name] for name in rest['precautions'])
    return f"The player's character rests {how} {where}" + (f', {taken}.' if taken else ', with no precautions.')


def prompt_text(lines: list[str]) -> str:
    return '## The rest (decided by the game; write it as it went)\n' + '\n'.join(
        f'- {line}' for line in lines) if lines else ''
