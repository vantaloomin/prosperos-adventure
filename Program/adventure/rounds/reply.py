"""The reply card: a turn waits on the user's character (docs/spec.md "Waiting and pauses": "The reply card"; Batch 2:
"The reply card offers Reply, Say nothing, or Let my character answer").

When someone addresses the user's character mid-turn, the turn pauses in AwaitingUser, keyed by seat, and the card
shows who is speaking, their line in full and the last two lines before it. The user answers one of three ways:

- **Reply**: their own words, which become their character's line as typed (untrusted text, fenced wherever it is
  read later).
- **Say nothing**: their character stays silent, and everyone present sees that.
- **Let my character answer**: an explicit opt-in for that one line. The Writer writes it in character from what the
  user declared this turn (adventure/rounds/writer.py `answer_for`), so nothing speaks for the user uninvited.

`ask` puts the card up from inside a step and `taken` reads the answer when that step runs again after
adventure/rounds/engine.py `answer`. Any step may ask: Converse when a character speaks to the user, and Resolve for
the one question an ambiguous move gets. The card is saved with the draft, so a restart resumes on it.
"""
from adventure.errors import require

KINDS = ('reply', 'silent', 'let_answer')
MOST_CHARS = 2000


def checked(body: dict) -> dict:
    """A reply as the card sends it, made safe to keep: a known kind, and words only for Reply."""
    kind = body.get('kind')
    require(kind in KINDS, 'Reply, say nothing, or let your character answer.', 422)
    text = str(body.get('text') or '').strip()
    if kind == 'reply':
        require(bool(text), 'Write what your character says, or pick another answer.', 422)
        require(len(text) <= MOST_CHARS, f'A reply runs to {MOST_CHARS} characters at most.', 422)
        return {'kind': kind, 'text': text}
    return {'kind': kind, 'text': ''}


def ask(turn, seat: str, speaker: str, line: str, context: list[str]):
    """Put the card up for `seat`: the turn pauses after the calling step returns."""
    turn.draft.wait_for(seat, speaker, line, context)


def taken(turn, seat: str) -> dict | None:
    """The answer `seat` gave the card, once: it is taken out of the draft, so a second question to the same seat in
    this turn waits for its own answer. A step keeps what it needs of it in its own staged data."""
    return turn.draft.replies.pop(seat, None)
