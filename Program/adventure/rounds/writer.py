"""The Writer: the one model that writes the story's prose (docs/spec.md "The turn loop" steps 6 and 8; Batch 4: "The
Writer's point of view has a default per mode").

Code decides and the Writer writes. It reads only its own context, built per mode by adventure/rounds/context.py
`writer` (adventure/rounds/context.py decides what the Writer may see in Play, Author and Watch; nothing here adds
a secret to it). Its calls in a round:

- **Who asks whom** in Converse (adventure/rounds/converse.py): pairs only, never what to ask.
- **Let my character answer**: one line for the user's character, from what the user declared this turn, written only
  when the user picked it on the reply card (adventure/rounds/reply.py).

Every reply from it goes through adventure/in_character.py, so a sentence that steps out of the story never reaches
the page. Text that came from a person or another model is fenced before it is shown to the Writer.
"""
from adventure import in_character
from adventure.providers.scheduling import CONVERSATION
from adventure.story import no_model
from adventure.text_models import config_for, key_for

# The Writer's model slot: the story narrator's until per-role slots name a Writer of their own.
JOB = 'story'
MOST_LINE_CHARS = 600


def config(connection) -> dict:
    found = config_for(connection, JOB)
    if found is None:
        raise no_model()
    return found


async def complete(turn, system: str, messages: list[dict]) -> str:
    """One whole reply from the Writer's model."""
    app = turn.app
    with app.database.connect() as connection:
        settings = config(connection)
    async with app.scheduler.reserve(settings, CONVERSATION):
        return ''.join([chunk.text async for chunk in app.provider.stream(settings, key_for(app.vault, settings),
                                                                         system, messages)])


def view(connection, turn) -> str:
    """What the Writer may know this turn, as the mode allows (adventure/rounds/context.py)."""
    from adventure.rounds import context  # the context builders decide what the Writer reads
    return context.writer(connection, turn.snapshot, turn.draft)


def fence_rule() -> str:
    from adventure.rounds import context
    return context.FENCE_RULE


def fence(label: str, text: str) -> str:
    """Text that came from a person or another model, marked as in-fiction content (as adventure/rounds/context.py
    fences it)."""
    return f'[[in-fiction: {label}]]\n{text.strip()}\n[[end: {label}]]'


def name_of(turn, key: str) -> str:
    seat = turn.snapshot.seat(key)
    return seat.name if seat else key


def one_line(text: str) -> str:
    """A spoken line as the Writer or an agent gave it: no wrapping quotes, nothing out of character, kept short."""
    text = in_character.clean(text or '').strip()
    if len(text) >= 2 and text[0] in '"“' and text[-1] in '"”':
        text = text[1:-1].strip()
    return text[:MOST_LINE_CHARS].strip()


ANSWER = """You are the Writer of a roleplaying game for adults. The user picked "Let my character answer" for one \
line: write what their character says back, in that character's own voice, from what the user declared they set \
out to do this turn and nothing more. Decide nothing else for them: no new plan, promise or secret. Reply with the \
spoken words only, one to three sentences, with no narration, no quotation marks and no name in front."""


async def answer_for(turn, seat: str, speaker: str, line: str) -> str:
    """The user's character's answer to `speaker`'s `line`, written by the Writer on the user's say-so; '' when the
    Writer gave nothing usable, which the caller treats as saying nothing."""
    with turn.database.connect() as connection:
        known = view(connection, turn)
    system = '\n\n'.join((ANSWER, fence_rule(), known))
    asked = (f'{fence("name", name_of(turn, speaker))} says to {fence("name", name_of(turn, seat))}:\n'
             f'{fence("line", line)}\n\nWrite the answer.')
    return one_line(await complete(turn, system, [{'role': 'user', 'content': asked}]))
