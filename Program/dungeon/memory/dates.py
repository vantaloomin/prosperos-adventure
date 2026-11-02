"""Resolve relative dates against when a statement was made, in the user's timezone (PRD M8).

Resolution is calendar-day granular: a span is [first local midnight, last local midnight) in UTC.
A phrase with more than one reasonable reading ("next Friday" said on a Monday) still resolves,
but is marked uncertain so the memory shows it and the user can correct it. A phrase with no
usable date ("soon", "one day") resolves to nothing rather than to a guess.
"""
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from dungeon.clock import zone

WEEKDAYS = ('monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday')
MONTHS = ('january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october',
          'november', 'december')
NUMBERS = {'a': 1, 'an': 1, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7,
           'eight': 8, 'nine': 9, 'ten': 10, 'eleven': 11, 'twelve': 12, 'twenty': 20, 'thirty': 30,
           'a couple of': 2, 'a few': 3, 'several': 3}
# Counts people use loosely; the resolved date is marked uncertain.
LOOSE = {'a few', 'several', 'a couple of'}
UNITS = {'day': 1, 'week': 7, 'month': 30, 'year': 365}

COUNT = r'(\d{1,3}|a couple of|a few|several|an?|one|two|three|four|five|six|seven|eight|nine|ten|eleven|' \
        r'twelve|twenty|thirty)'
DAY = '(' + '|'.join(WEEKDAYS) + ')'
MONTH = '(' + '|'.join(MONTHS) + ')'

PHRASE = re.compile(
    r'\b(?:today|tonight|this (?:morning|afternoon|evening)|tomorrow|yesterday|this week|next week|last week|'
    r'this weekend|next weekend|last weekend|this month|next month|last month|this year|next year|last year|'
    rf'(?:on |this |next |last |until |till |by )?{DAY}|in {COUNT} (?:day|week|month|year)s?|'
    rf'{COUNT} (?:day|week|month|year)s? ago|\d{{4}}-\d{{2}}-\d{{2}}|{MONTH} \d{{1,2}}(?:st|nd|rd|th)?|'
    rf'\d{{1,2}}(?:st|nd|rd|th)? (?:of )?{MONTH}|in {MONTH}|(?:in )?(?:19|20)\d{{2}})\b', re.IGNORECASE)


@dataclass(frozen=True)
class Span:
    start: date
    end: date  # exclusive
    certain: bool = True
    phrase: str = ''


def local_day(stated: datetime, timezone: str) -> date:
    return stated.astimezone(zone(timezone)).date()


def instant(day: date, timezone: str) -> datetime:
    return datetime.combine(day, time(0), zone(timezone))


def count(word: str) -> tuple[int, bool]:
    word = word.lower()
    return (int(word), True) if word.isdigit() else (NUMBERS[word], word not in LOOSE)


def week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


def add_months(day: date, months: int) -> date:
    month = day.month - 1 + months
    year, month = day.year + month // 12, month % 12 + 1
    return date(year, month, 1)


def weekday_span(prefix: str, name: str, today: date, past: bool) -> Span:
    """`on Friday` is the coming one (or the latest for past tense); `next Friday` is ambiguous midweek."""
    target = WEEKDAYS.index(name)
    ahead = (target - today.weekday()) % 7
    if prefix == 'last' or (past and prefix in {'', 'on'}):
        behind = (today.weekday() - target) % 7 or 7
        day = today - timedelta(days=behind)
        return Span(day, day + timedelta(days=1), prefix != 'last' or behind > 1)
    ahead = ahead or 7
    if prefix == 'next':
        # Said earlier in the same week, "next Friday" can mean this Friday or the one after.
        day = today + timedelta(days=ahead)
        return Span(day, day + timedelta(days=1), certain=day >= week_start(today) + timedelta(days=7))
    day = today + timedelta(days=ahead)
    if prefix in {'until', 'till', 'by'}:
        return Span(today, day + timedelta(days=1))
    return Span(day, day + timedelta(days=1))


def month_day(month: str, number: int, today: date, past: bool) -> Span | None:
    index = MONTHS.index(month.lower()) + 1
    try:
        day = date(today.year, index, number)
    except ValueError:
        return None
    if past and day > today:
        day = date(today.year - 1, index, number)
    elif not past and day < today:
        day = date(today.year + 1, index, number)
    return Span(day, day + timedelta(days=1))


FIXED = {
    'today': (0, 1), 'tonight': (0, 1), 'this morning': (0, 1), 'this afternoon': (0, 1),
    'this evening': (0, 1), 'tomorrow': (1, 2), 'yesterday': (-1, 0),
}


def relative_span(text: str, today: date) -> Span | None:
    """Fixed words and calendar periods relative to today."""
    if text in FIXED:
        start, end = FIXED[text]
        return Span(today + timedelta(days=start), today + timedelta(days=end))
    monday = week_start(today)
    periods = {
        'this week': (today, monday + timedelta(days=7)),
        'next week': (monday + timedelta(days=7), monday + timedelta(days=14)),
        'last week': (monday - timedelta(days=7), monday),
        'this weekend': (monday + timedelta(days=5), monday + timedelta(days=7)),
        'next weekend': (monday + timedelta(days=12), monday + timedelta(days=14)),
        'last weekend': (monday - timedelta(days=2), monday),
        'this month': (today, add_months(today, 1)),
        'next month': (add_months(today, 1), add_months(today, 2)),
        'last month': (add_months(today, -1), add_months(today, 0)),
        'this year': (today, date(today.year + 1, 1, 1)),
        'next year': (date(today.year + 1, 1, 1), date(today.year + 2, 1, 1)),
        'last year': (date(today.year - 1, 1, 1), date(today.year, 1, 1)),
    }
    if text in periods:
        start, end = periods[text]
        return Span(start, end)
    return None


def offset_span(text: str, today: date) -> Span | None:
    """`in three weeks` and `ten years ago`."""
    match = re.fullmatch(rf'in {COUNT} (day|week|month|year)s?', text) or \
        re.fullmatch(rf'{COUNT} (day|week|month|year)s? ago', text)
    if not match:
        return None
    number, certain = count(match.group(1))
    days = number * UNITS[match.group(2)] * (-1 if text.endswith('ago') else 1)
    day = today + timedelta(days=days)
    if match.group(2) in {'month', 'year'}:
        # A month or a year away names a period, not one exact day.
        return Span(day - timedelta(days=15), day + timedelta(days=15), certain=False)
    return Span(day, day + timedelta(days=1), certain)


def calendar_span(text: str, today: date, past: bool) -> Span | None:
    """Absolute dates: ISO dates, `12 October`, `in March` and a bare year."""
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}', text):
        try:
            day = date.fromisoformat(text)
        except ValueError:
            return None
        return Span(day, day + timedelta(days=1))
    if match := re.fullmatch(rf'{MONTH} (\d{{1,2}})(?:st|nd|rd|th)?', text):
        return month_day(match.group(1), int(match.group(2)), today, past)
    if match := re.fullmatch(rf'(\d{{1,2}})(?:st|nd|rd|th)? (?:of )?{MONTH}', text):
        return month_day(match.group(2), int(match.group(1)), today, past)
    if match := re.fullmatch(rf'in {MONTH}', text):
        start = month_day(match.group(1), 1, today.replace(day=1), past)
        return Span(start.start, add_months(start.start, 1)) if start else None
    if match := re.fullmatch(r'(?:in )?((?:19|20)\d{2})', text):
        year = int(match.group(1))
        return Span(date(year, 1, 1), date(year + 1, 1, 1))
    return None


def resolve(text: str, stated: datetime, timezone: str, past: bool = False) -> Span | None:
    """The first date phrase in `text`, resolved against the statement's own time.

    `past` says the statement is about the past, so `on Friday` means the latest Friday.
    """
    match = PHRASE.search(text)
    if not match:
        return None
    phrase = ' '.join(match.group(0).lower().split())
    today = local_day(stated, timezone)
    weekday = re.fullmatch(rf'(?:(on|this|next|last|until|till|by) )?{DAY}', phrase)
    if weekday:
        span = weekday_span(weekday.group(1) or '', weekday.group(2), today, past)
    else:
        span = relative_span(phrase, today) or offset_span(phrase, today) or calendar_span(phrase, today, past)
    return None if span is None else Span(span.start, span.end, span.certain, phrase)


def bounds(span: Span, timezone: str) -> tuple[datetime, datetime]:
    return instant(span.start, timezone), instant(span.end, timezone)
