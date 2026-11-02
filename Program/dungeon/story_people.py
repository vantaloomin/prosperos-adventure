"""The people the user has met in their own story (Story mode, docs/story.md), kept apart from every companion.

Someone present in the scene is met once their name comes up: the narrator voices them giving it, or the
user uses it. Each local day they come up counts as one meeting. A few sentences of the story about them
are kept as notes, so the narrator remembers them the next time they are in the scene, however far back
the story has been trimmed. Townsfolk keep no memories of their own; this is the user's side only.

Their voice stays theirs (ported from Prospero's Companion 1.0, companion/memory/voice.py): lines the narration gave
someone, quoted in a paragraph that names only them, are kept (`heard`), and the narrator is shown one or two from
earlier meetings, so they keep sounding like themselves however far back the story is trimmed or whichever model
narrates. Rules only, no model call.
"""
import re
from datetime import date

from dungeon import feelings
from dungeon.database import decode, encode, many, optional

NOTES = 8
NOTE_CHARS = 240
SENTENCE = re.compile(r'[^.!?\n]+[.!?]["”’)]?')
# Their voice: lines kept, lines shown, and how long a line must be to show a voice.
VOICE_KEPT, VOICE_SHOWN = 12, 2
LINE_CHARS, LINE_MIN_CHARS, LINE_MIN_WORDS = 160, 25, 5
QUOTE = re.compile(r'"([^"\n]+)"|“([^”\n]+)”')
# The player character speaking in a paragraph ("you say", "you ask him"): its quotes may be theirs.
YOU_SPEAK = re.compile(r'\byou\s+(?:\w+\s+)?(?:say|said|ask|asked|tell|told|reply|replied|answer|answered|mutter|'
                       r'whisper|call|shout|add|snap|murmur)\b', re.IGNORECASE)


def known(connection) -> dict[str, dict]:
    """Everyone met, with their bond to the character if they have one ('earned' or 'sworn', dungeon/bonds.py) and
    unless it is broken or lost."""
    return {row['key']: row | {'notes': decode(row['notes'])} for row in many(
        connection, "SELECT p.*, CASE WHEN f.state IN ('dead', 'turned') THEN NULL ELSE b.how END AS bond "
                    'FROM story_people p LEFT JOIN story_bonds b ON b.key=p.key LEFT JOIN story_fates f ON f.key=p.key '
                    'ORDER BY p.last_met_at DESC')}


def named(sheet: dict, text: str) -> bool:
    """Their given name (or full name) as a word in the text, capitalized as a name is."""
    return any(name and re.search(rf'(?<![\w-]){re.escape(name)}(?![\w-])', text)
               for name in (sheet.get('full'), sheet.get('name')))


def about(sheet: dict, text: str, limit: int = 2) -> list[str]:
    """The sentences of the text that name them, trimmed for the notes."""
    found = [sentence.strip() for sentence in SENTENCE.findall(text) if named(sheet, sentence)]
    return [sentence if len(sentence) <= NOTE_CHARS else sentence[:NOTE_CHARS - 1].rstrip() + '…'
            for sentence in found[:limit]]


def meet(connection, sheet: dict, city_id: str, now: str, day: date, notes=()):
    """Record that the user met this person (again): one meeting per local day, the newest notes kept.
    Other features that put the user with someone in the story (a date, say) call this too."""
    row = optional(connection, 'SELECT * FROM story_people WHERE key=?', (sheet['key'],))
    if row is None:
        connection.execute(
            'INSERT INTO story_people (key, city_id, name, first_met_at, last_met_at, last_day, meetings, notes) '
            'VALUES (?, ?, ?, ?, ?, ?, 1, ?)', (sheet['key'], city_id, sheet['full'], now, now, day.isoformat(),
                                                 encode([note for note in notes][-NOTES:])))
        return
    kept = decode(row['notes'])
    kept += [note for note in notes if note not in kept]
    connection.execute('UPDATE story_people SET last_met_at=?, last_day=?, meetings=meetings+?, notes=? WHERE key=?',
                       (now, day.isoformat(), int(row['last_day'] != day.isoformat()), encode(kept[-NOTES:]),
                        sheet['key']))


def note_exchange(connection, people: list[dict], city_id: str, said: str, reply: str, now: str, day: date):
    """After the narrator's reply: everyone present whose name came up has met the user, and keeps what they said."""
    lines = heard([person['sheet'] for person in people], reply)
    for person in people:
        sheet = person['sheet']
        if named(sheet, reply) or named(sheet, said):
            meet(connection, sheet, city_id, now, day, about(sheet, reply))
            hear(connection, sheet['key'], lines.get(sheet['key'], []), day)


# Their voice -------------------------------------------------------------------------------------------

def line_of(quote: str) -> str | None:
    """A quoted line as kept: the first sentence or two, or None when it is too short to show a voice."""
    text = ' '.join(quote.split()).strip(' ,')
    if len(text) > LINE_CHARS:
        text = text[:LINE_CHARS].rsplit(' ', 1)[0] + '…'
    return text if len(text) >= LINE_MIN_CHARS and len(text.split()) >= LINE_MIN_WORDS else None


def heard(sheets: list[dict], reply: str) -> dict[str, list[str]]:
    """{key: lines} for the people the narration quotes: a quote counts as someone's when its paragraph names only
    them of everyone present and the player character is not speaking in it."""
    found: dict[str, list[str]] = {}
    for paragraph in re.split(r'\n\s*\n', reply):
        outside = QUOTE.sub(' ', paragraph)
        speakers = [sheet for sheet in sheets if named(sheet, outside)]
        if len(speakers) != 1 or YOU_SPEAK.search(outside):
            continue
        for match in QUOTE.finditer(paragraph):
            if line := line_of(match.group(1) or match.group(2)):
                found.setdefault(speakers[0]['key'], []).append(line)
    return found


def same(text: str) -> str:
    """A line as compared with the others: the same words said twice are one line."""
    return ' '.join(re.findall(r"[\w']+", text.casefold()))


def hear(connection, key: str, lines: list[str], day: date):
    if not lines:
        return
    row = optional(connection, 'SELECT voice FROM story_people WHERE key=?', (key,))
    kept = decode(row['voice']) if row else []
    known = {same(item['text']) for item in kept}
    for line in lines:
        if same(line) not in known:
            known.add(same(line))
            kept.append({'text': line, 'day': day.isoformat()})
    connection.execute('UPDATE story_people SET voice=? WHERE key=?', (encode(kept[-VOICE_KEPT:]), key))


def voice_text(row: dict, today: str | None = None) -> str:
    """One or two of their lines from days before `today` (else their latest meeting day), so the narrator keeps their
    voice without repeating what the recent story already shows. The pick changes only when the lines do, steadying
    the prompt."""
    before = today or row['last_day']
    earlier = [item['text'] for item in decode(row.get('voice') or '[]') if item['day'] < before]
    if not earlier:
        return ''
    step = max(1, len(earlier) // VOICE_SHOWN)
    shown = earlier[::-1][::step][:VOICE_SHOWN]
    return (' How they sound (lines they said before; keep this voice in new words, never reuse these): '
            + ' / '.join(f'"{line}"' for line in shown) + '.')


def remembered(row: dict | None, today: str | None = None) -> str:
    """What the narrator is told about someone the user has met, or '' for a stranger."""
    if not row:
        return ''
    times = 'once' if row['meetings'] == 1 else 'twice' if row['meetings'] == 2 else f"{row['meetings']} times"
    notes = ' '.join(row['notes'][-4:])
    impressions = '; '.join(decode(row.get('impressions') or '[]'))
    felt = feelings.text(row)
    return f" The user has met them {times} and knows their name; last on {row['last_day']}." + \
        (f' From before: {notes}' if notes else '') + voice_text(row, today) + (f' {felt}' if felt else '') + \
        (f' Their impressions of the character: {impressions}.' if impressions else '') + \
        (' They are bonded to the character: they would stand by them, and the character can call on them.'
         if row.get('bond') else '')
