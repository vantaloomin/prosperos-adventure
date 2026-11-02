"""The story clock (requirements "Time and travel": story time, with a per-world option).

Once a campaign starts, the story keeps its own time: each line the player sends moves it on by what they did (a
few minutes of talk, a walk across town, a night's sleep) and the scene, the townsfolk and deadlines follow it. A
story begun before the clock existed, or with no campaign start, lives on the app clock as Companion did.

A world can live in real time instead (the tier file's `clock`, Havenbrooke's; the Table's `clock` overrides it):
then the real time since the last line also passes before the next one, so the world keeps moving while the app is
closed, up to MOST_AWAY at once, and the narrator hears how long the character was away (AWAY or more).

The time is game state, branched with the story (dungeon/timeline.py SAVED).
"""
import re
from datetime import datetime, timedelta

from dungeon.database import optional

TURN_MINUTES = 10
TALK_MINUTES = 5
# Moving within a city, and to another one, until the travel map decides journeys.
ACROSS_TOWN_MINUTES = 20
ANOTHER_CITY_MINUTES = 6 * 60
WORDS = {'one': 1, 'an': 1, 'a': 1, 'another': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7,
         'eight': 8, 'nine': 9, 'ten': 10, 'eleven': 11, 'twelve': 12, 'few': 3, 'couple of': 2}
# Real time: the most that passes at once however long the app was closed (30 days), and the gap the narrator is told
# about (an hour).
MOST_AWAY, AWAY = 30 * 24 * 60, 60
# "The day" runs until DAY_END local, at most DAY_SPAN; begun in the evening, the day is done: LATE_DAY passes.
DAY_SPAN, DAY_END, LATE_DAY = 10 * 60, 19, 60
# (pattern, minutes), first match wins.
SPANS = (
    (r'\b(sleep|go to bed|turn in|rest for the night|bed down|camp for the night)\b', 8 * 60),
    (r'\b(nap|doze|rest a while|take a rest)\b', 60),
    # A stretch of the day spent at something: "I spend the day felling trees and come back at dusk".
    (r'\b(spend|spends|spending|work|works|working|pass|passes|passing|take|takes|taking)\b.*'
     r'\b(the|all|a|an|the whole|a whole)[- ]day\b',
     DAY_SPAN),
    (r'\b(spend|spends|spending|work|works|working|pass|passes|passing)\b.*\b(the|all) (morning|afternoon)\b',
     4 * 60),
    (r'\b(spend|spends|spending|work|works|working|pass|passes|passing)\b.*\b(the|all) evening\b',
     3 * 60),
    (r'\b(travel|ride|walk|head|hike|journey|march)\b.*\b(to|toward|towards|into|out of)\b', 30),
)


def now(connection, clock) -> datetime:
    row = optional(connection, 'SELECT at FROM story_clock WHERE id=1')
    return datetime.fromisoformat(row['at']) if row else clock.now()


def running(connection) -> bool:
    return optional(connection, 'SELECT at FROM story_clock WHERE id=1') is not None


def start(connection, at: datetime):
    connection.execute('INSERT INTO story_clock (id, at) VALUES (1, ?) ON CONFLICT(id) DO UPDATE SET at=excluded.at',
                       (at.isoformat(),))


def advance(connection, minutes: int):
    row = optional(connection, 'SELECT at FROM story_clock WHERE id=1')
    if row and minutes > 0:
        start(connection, datetime.fromisoformat(row['at']) + timedelta(minutes=minutes))


def caught_up(connection, wall: datetime, living: bool) -> int:
    """Real time (a world that keeps moving while the app is closed): the minutes since the story last caught up,
    at most MOST_AWAY, when the world lives in real time, else 0. The mark moves to `wall` either way, so turning
    real time on later starts from then."""
    row = optional(connection, 'SELECT at FROM story_real WHERE id=1')
    connection.execute('INSERT INTO story_real (id, at) VALUES (1, ?) ON CONFLICT(id) DO UPDATE SET at=excluded.at',
                       (wall.isoformat(),))
    if not row or not living or not running(connection):
        return 0
    return max(0, min(MOST_AWAY, int((wall - datetime.fromisoformat(row['at'])).total_seconds() // 60)))


def waited(text: str) -> int | None:
    """'I wait two hours', 'wait 20 minutes', 'I work the saws for three hours' or 'for three more hours', in
    minutes."""
    numbers = '|'.join(sorted(WORDS, key=len, reverse=True))
    match = re.search(rf'\b(?:wait\w*\b.*?|for\s+)(?:another\s+|an?\s+extra\s+)?\b(\d+|{numbers})\s+'
                      rf'(?:more\s+|extra\s+|further\s+)?(hour|minute)s?\b', text, re.I)
    if not match:
        return None
    amount = int(match.group(1)) if match.group(1).isdigit() else WORDS[match.group(1).lower()]
    return min(amount * (60 if match.group(2).lower() == 'hour' else 1), 24 * 60)


# "I wait until evening": the hour a time of day starts.
HOURS = {'dawn': 6, 'sunrise': 6, 'first light': 6, 'morning': 7, 'noon': 12, 'midday': 12, 'afternoon': 13,
         'evening': 17, 'dusk': 18, 'sunset': 18, 'nightfall': 20, 'dark': 20, 'night': 20, 'midnight': 0}


def until(text: str, local: datetime) -> int | None:
    """'I wait until evening', 'wait till dusk', 'wait until she opens for the evening': the minutes from the local
    time to the next such hour."""
    names = '|'.join(sorted(HOURS, key=len, reverse=True))
    match = re.search(rf'\b(?:wait\w*|sit\w*|stay\w*|linger\w*|loiter\w*)\b.*?\b(?:until|till|til)\b\s+'
                      rf'(?:[\w\']+\s+){{0,5}}?(?:the\s+)?({names})\b', text, re.I)
    if not match:
        return None
    target = local.replace(hour=HOURS[match.group(1).lower()], minute=0, second=0, microsecond=0)
    if target <= local:
        target += timedelta(days=1)
    return int((target - local).total_seconds() // 60)


def minutes_for(text: str, rolled: bool, local: datetime | None = None) -> int:
    """How long a line of the player's takes: talk is quick, a risky action takes a while, rest takes the night, and
    waiting until a time of day takes until then (from `local`, the city's time now)."""
    if (minutes := waited(text)) is not None:
        return minutes
    if local is not None and (minutes := until(text, local)) is not None:
        return minutes
    for pattern, minutes in SPANS:
        if re.search(pattern, text, re.I):
            return day_left(minutes, local)
    return TURN_MINUTES if rolled else TALK_MINUTES


def day_left(minutes: int, local: datetime | None) -> int:
    """A span as long as it really runs: 'the day' begun at 16:10 runs to the evening, not past midnight."""
    if minutes != DAY_SPAN or local is None:
        return minutes
    left = int((local.replace(hour=DAY_END, minute=0, second=0, microsecond=0) - local).total_seconds() // 60)
    return min(DAY_SPAN, left) if left >= LATE_DAY else LATE_DAY


def spent(text: str, local: datetime | None = None) -> int:
    """A stretch a line spends at something ('for three hours', 'the afternoon', 'the day'), in minutes; 0 for none."""
    if (minutes := waited(text)) is not None:
        return minutes
    return next((day_left(span, local) for pattern, span in SPANS[2:5] if re.search(pattern, text, re.I)), 0)
