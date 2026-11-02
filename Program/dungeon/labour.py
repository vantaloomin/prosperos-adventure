"""Day labour (requirements "Shops and services": money comes in as well as goes out).

A line that spends a stretch of the day working in a town ("I spend the day hauling logs for the yard", "I work the
saws for three hours") is paid the town's day wage (the `day-wage` price, dungeon/happenings.py wage), pro rata for
the hours, up to a full day. The story clock has already passed the time (dungeon/story_clock.py SPANS and waited);
this only pays it, once for each line (story_cards, scene 'work').
"""
import re

from dungeon import inventory, story_clock

DAY_MINUTES = 10 * 60
# Under an hour of work earns nothing worth counting.
LEAST_MINUTES = 60
WORKING = re.compile(r'\b(haul\w*|felling|chop\w*|saw(s|ing)?|dig\w*|labou?r\w*|muck\w* out|stack\w*|load\w*|'
                     r'unload\w*|carry\w*|work\w*|hire[sd]? on|odd jobs?|job|shift|graft\w*|toil\w*)\b', re.I)
# Work that is not for hire: on the character's own things, or study.
OWN = re.compile(r'\b(on (my|his|her|their) own|for myself|my (own )?(gear|sword|blade|journal|notes)|study\w*|'
                 r'homework|coursework|out (at|in) the gym|work\w* out)\b', re.I)


def minutes(text: str, passed: int | None = None) -> int:
    """The minutes of paid work in a line: a stretch of the day, or so many hours, spent working, and no more than
    the time the line `passed` on the story clock; 0 for none."""
    if not WORKING.search(text) or OWN.search(text):
        return 0
    spent = story_clock.spent(text)
    spent = spent if passed is None else min(spent, passed)
    return min(spent, DAY_MINUTES) if spent >= LEAST_MINUTES else 0


def pay(connection, text: str, wage: int, currency: dict, passed: int | None = None) -> list[str]:
    """The wage for the line's work, into the purse; the line that tells the narrator."""
    worked = minutes(text, passed)
    if not worked:
        return []
    earned = wage * worked // DAY_MINUTES
    inventory.set_purse(connection, inventory.purse(connection) + earned)
    hours = worked // 60
    return [f"Paid for {hours} hour{'s' if hours != 1 else ''} of work: {inventory.money_text(earned, currency)} "
            f"(the going day wage here is {inventory.money_text(wage, currency)}), now in the purse. Whoever hired the "
            "character pays it at the end; the narrator may not change the sum."]


def prompt_text(lines: list[str]) -> str:
    return '## Work for hire (decided by the game)\n' + '\n'.join(f'- {line}' for line in lines) if lines else ''
