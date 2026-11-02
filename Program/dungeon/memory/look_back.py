"""They can ask to remember more (Feature Hit List #39): one extra look through memory when a reply needs it.

Recall runs once before a reply (dungeon/memory/context.py, "Possibly relevant memories"). When the user's message
points at the past ("remember when", "last summer", "you told me") two things can add to it:

- With no model call: when that first recall comes back thin, the app widens the search itself before the reply,
  with the user's last few messages for words and without holding back what came up lately.
- Once per reply: the companion's reply may start with a hidden request instead, `[[recall: the ferry trip]]`. The
  app catches it before any text is shown (`Lookout`), looks again with those words, adds what it found as a note
  at the end of the prompt (so prompt caching still works) and asks once more, without the option to ask again. So
  the worst case is two model calls for that reply. A text marker, not tool calling, because many local models
  handle tools poorly. The request never shows in chat; if nothing more turns up, they answer with what they have.

The Memory setting `recall_more` (on by default) turns the second part off; the widened search always runs. A model
that asks in more than a quarter of the replies it is offered this stops being offered it until the app restarts
(`Rates`), and a request that turns up anywhere else in a reply is cut out, matched loosely.
"""
import logging
import re

LOG = logging.getLogger(__name__)

PAST = re.compile(
    r"\b(?:remember(?:s|ed)?|recall|back when|that time|the time (?:we|you|i)|last (?:year|summer|winter|spring|"
    r"fall|autumn|month|week|time)|(?:years?|months?|weeks?) ago|used to|you (?:said|told me|mentioned|promised)|"
    r"i (?:told|said to|mentioned to) you|when we|we (?:went|had|did|talked)|forgot|forget)\b", re.IGNORECASE)
# Fewer recalled items than this (besides pinned ones) is a thin first recall.
THIN = 2
# The user's own recent messages added to a widened search.
WIDEN_MESSAGES = 3
# A request, matched loosely because small models get it slightly wrong: "[[recall: x]]", "[recall x]", "[[Recall: x]".
MARKER = re.compile(r'\[\[?\s*recall\b\s*:?\s*([^\]\n]{0,200}?)\s*\]\]?', re.IGNORECASE)
# The start of one, still arriving.
PARTIAL = re.compile(r'\[\[?\s*(?:r(?:e(?:c(?:a(?:l(?:l(?:\b\s*:?\s*[^\]\n]{0,200}\]?)?)?)?)?)?)?)?', re.IGNORECASE)
# One the reply ended inside, cut off before it closed (at the model's length limit, say).
UNCLOSED = re.compile(r'\[\[?\s*recall\b\s*:?\s*([^\]\n]{0,200}?)\s*\]?$', re.IGNORECASE)
# A start longer than this that never closes the request is ordinary text.
HOLD_LIMIT = 260
# The chat says it is checking older memories once the second look has taken this long (seconds).
SHOW_AFTER = 1.0
# Once a model has been offered the extra look this many times, it stops being offered to a model that asks for it
# in more than RATE_LIMIT of its replies: each request doubles the wait for that reply.
RATE_AFTER = 20
RATE_LIMIT = 0.25
ASK = ("If the user is talking about something from before that is not in your notes or the conversation, and you "
       "need the details to answer well, you may reply with only [[recall: a few words to look up]] instead of a "
       "reply. The app will look through your memories and earlier conversations and ask you again, once. "
       "Otherwise just reply as usual, and never mention this.")
FOUND = ("You asked to remember more about «{query}». What the app found in your memories and earlier "
         "conversations:\n{lines}\nNow write your reply, using this where it fits. Do not ask to look anything up "
         "again.")
NOTHING = ("You asked to remember more about «{query}», but nothing more was found. Reply with what you know; if you "
           "don't remember, say so the way a person would. Do not ask to look anything up again.")


def points_back(text: str) -> bool:
    return bool(PAST.search(text or ''))


def found_note(query: str, lines: list[str]) -> str:
    return FOUND.format(query=query, lines='\n'.join(lines)) if lines else NOTHING.format(query=query)


class Lookout:
    """Watches a streamed reply for requests to remember more, so none is ever shown. One at the very start, when
    `active` and not `strip`, is the request: the rest of the reply is dropped and `query` holds what to look up.
    Any other, anywhere in the reply, is cut out (the second try may not ask again)."""

    def __init__(self, active: bool = True, strip: bool = False):
        self.asking = active and not strip
        self.started = False
        self.last, self.after_cut = ' ', False
        self.held = ''
        self.query: str | None = None

    def feed(self, piece: str) -> str:
        if self.query is not None:
            return ''
        self.held += piece
        shown = []
        while self.held:
            at = self.held.find('[')
            shown.append(self.take(len(self.held) if at < 0 else at))
            if not self.held:
                break
            found = MARKER.match(self.held)
            if found is None or waiting(self.held, found):
                if self.could_be(self.held):
                    break
                shown.append(self.take(1))
            elif self.cut(found):
                return ''
        return ''.join(shown)

    def cut(self, found) -> bool:
        """Takes a request out of the held text; True when it is the reply's request to look again."""
        if self.asking and not self.started:
            self.query, self.held = found.group(1).strip() or 'that', ''
            return True
        self.held, self.after_cut = self.held[found.end():], True
        return False

    def take(self, count: int) -> str:
        """The next `count` characters, shown; spaces before the reply starts are dropped."""
        text, self.held = self.held[:count], self.held[count:]
        if not self.started:
            text = text.lstrip()
            self.started = bool(text)
        if self.after_cut and text:
            # The space before a cut request is kept; the one after it goes.
            text = text.lstrip(' ') if self.last in ' \n' else text
            self.after_cut = not text
        self.last = text[-1:] or self.last
        return text

    def could_be(self, text: str) -> bool:
        """Whether the held text could still become a request."""
        partial = PARTIAL.match(text)
        return partial is not None and partial.end() == len(text) and len(text) <= HOLD_LIMIT

    def flush(self) -> str:
        if self.query is not None:
            return ''
        text, self.held = self.held, ''
        found = MARKER.match(text) or UNCLOSED.match(text)
        if found and self.asking and not self.started:
            self.query = found.group(1).strip() or 'that'
            return ''
        return tidy(UNCLOSED.sub('', MARKER.sub('', text)))


def waiting(text: str, found) -> bool:
    """A request opened with two brackets has closed with one so far: the second may still be on its way."""
    return found.end() == len(text) and text.startswith('[[') and not found.group(0).endswith(']]')


def tidy(text: str) -> str:
    return re.sub(r'[ \t]{2,}', ' ', text)


class Rates:
    """How often each model asked to look again when offered, while the app runs."""

    def __init__(self):
        self.offered: dict[str, int] = {}
        self.asked: dict[str, int] = {}
        self.noted: set[str] = set()

    def allowed(self, model: str) -> bool:
        offered = self.offered.get(model, 0)
        too_often = offered >= RATE_AFTER and self.asked.get(model, 0) / offered > RATE_LIMIT
        if too_often and model not in self.noted:
            self.noted.add(model)
            LOG.info('Stopped offering a second look through memory to a model that asked for it too often.')
        return not too_often

    def count(self, model: str, asked: bool):
        self.offered[model] = self.offered.get(model, 0) + 1
        self.asked[model] = self.asked.get(model, 0) + int(asked)


RATES = Rates()
