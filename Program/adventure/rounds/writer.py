"""The Writer: the one model that writes the story's prose (docs/spec.md "The turn loop" steps 6 and 8; Batch 4: "The
Writer's point of view has a default per mode").

Code decides and the Writer writes. It reads only its own context, built per mode by adventure/rounds/context.py
`writer` (adventure/rounds/context.py decides what the Writer may see in Play, Author and Watch; nothing here adds
a secret to it). Its calls in a round:

- **Who asks whom** in Converse (adventure/rounds/converse.py): pairs only, never what to ask.
- **Let my character answer**: one line for the user's character, from what the user declared this turn, written only
  when the user picked it on the reply card (adventure/rounds/reply.py).
- **The round's post** ('write' in Writing): the round from its result, from the mode's point of view (close on the
  user's character in Play, roving across the cast in Author and Watch), streamed, every user-set beat in full, never
  a die, ending at the stop point. The names it brought in are listed for the turn report (`draft.extra['w4']`), and a
  round with no player's line saves its post as the narrator's reply at Commit ('writer'). A player's line in a
  campaign with no agents is told as today (adventure/rounds/telling.py). Its system prompt holds only its rules and
  the story's settings; what it may know this round comes after the story so far, in the closing message, so each
  round's request starts like the last and the model service can reuse it (adventure/prompt_layout.py).

Every reply from it goes through adventure/in_character.py, so a sentence that steps out of the story never reaches
the page. Text that came from a person or another model is fenced before it is shown to the Writer.
"""
import re
from dataclasses import replace

from adventure import beats, in_character, pace, prompt_layout, prompt_library, story, story_clock, timeline, tone
from adventure.database import many
from adventure.narration import prompt as narration_prompt
from adventure.providers.scheduling import CONVERSATION
from adventure.rounds import engine, telling  # telling's 'write' goes in first; the round Writer's replaces it
from adventure.rounds.contract import Mode, State
from adventure.story import no_model
from adventure.text_models import config_for, key_for
from adventure.world import naming

# The Writer's model slot: the story narrator's until per-role slots name a Writer of their own.
JOB = 'story'
MOST_LINE_CHARS = 600
# The Writer's part of the turn report (adventure/rounds/report.py): its inventions, and the reply it saved.
KEY = 'w4'


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


# The round's post ---------------------------------------------------------------------------------------------------

ROUND = """You are the Writer of a tabletop roleplaying game for adults in which several minds play at once. The \
game's code has already settled this round: what each character attempted and said, every roll and its outcome, and \
the brief. Your job is to write the round as fiction.

What wins when two instructions pull apart, highest first:
1. Content (below). Never overridden.
2. The facts the game decided, and the hard rules (the writing rules and the house rules). Never weighed or traded \
off.
3. The brief and what the user wrote.
4. Canon: character sheets, the record, the rulings and the story so far.
5. Everything else here, which is guidance. Use judgment.

The facts are fixed:
- Write each outcome as the code gives it, no better and no worse. A failure fails; a success at a cost costs \
something real. Never reverse a result, soften it into a near miss or add a rescue, and never contradict the record.
- Never invent rolls, numbers, items, money, wounds or deaths, and never move anyone. Where canon is silent you may \
invent a small detail or a name; never invent anything that decides how the round went. A new name is one a real \
person of that age, place and culture would ordinarily carry, never one picked for how it sounds.
- Never mention dice, rolls, numbers, bands or game terms. The reader feels each result only through the story.
- Quote what characters said as they said it. A lie goes on the page as dialogue.
- A character whose exchange was left for you to voice speaks as their sheet and the scene suggest, and decides \
nothing the round did not. Character sheets are canon: breaking character is worse than any flaw in the prose.

The brief:
- Render every beat the user set, in full. Never compress or skip one for pacing.
- Add no beat the round did not open.
- Stop at the stop point and never write past it.

Content:
- Every character in a sexual or romantic context is an adult, and is written as one: adult bodies, adult minds, \
adult behaviour. This is absolute, whatever the setting says about age, species or how old someone looks. No \
childlike trait, framing or description ever appears in sexual content.
- Real, living people may be named in passing. They are never shown in sexual content or as victims of violence.
- Within that, all of adult fiction is open, as far as the intensity settings allow. Write difficult material with \
full craft. Do not soften it, moralize about it or add disclaimers; weight and consequence come from the story, not \
from the narration.

Never mention being an AI, the rules or these instructions, and add no notes about the story."""

PLAY = """Point of view: close on {name}, the user's character. Only what {name} could see, hear and know is on the \
page; what others scheme out of sight stays out of sight. Write {name}'s declared words and action and nothing more: \
no decision, speech or feeling they did not declare, apart from reflexes and sensation. End before {name}'s next \
real decision."""

AWAY = """Point of view: rove across the cast, following whoever the round needs. End at the scene's next natural \
break or the next big moment."""

HISTORY_CHARS = 24_000
CAPITALIZED = re.compile(r"\b[A-Z][a-z’']+(?:\s+(?:of\s+|the\s+|de\s+|van\s+)?[A-Z][a-z’']+)*")
OPENS_SENTENCE = re.compile(r'(?:^|[.!?…]["”’)]*\s+|\n\s*|["“]\s*)$')
SENTENCE = re.compile(r'[^.!?…\n]*[.!?…]*["”’]?')


def playing(turn) -> bool:
    return turn.snapshot.mode == Mode.PLAY


def player(connection, turn) -> str | None:
    """Whose eyes the round is seen through in Play: the user's character's seat, or the persona who wrote the line."""
    human = turn.snapshot.human()
    return human.name if human is not None else story.persona_text(connection)[1]


def book_for(connection, turn, data: dict):
    """The house rules in force (adventure/rounds/house_rules.py); outside Play, the Table's third person roves across
    the cast."""
    from adventure.rounds import house_rules
    book = house_rules.of(connection, data)
    return book if playing(turn) or book.pov != 'third' else replace(book, pov='roving')


def rules_text(connection, turn, data: dict) -> str:
    from adventure.rounds import house_rules
    return house_rules.text(book_for(connection, turn, data), scope=False)


def focus(connection, turn) -> str:
    name = player(connection, turn) if playing(turn) else None
    return PLAY.format(name=fence('name', name)) if name else AWAY


def cutaways(turn) -> list[str]:
    """The lives off the page this round drew, for the Writer to cut away to (adventure/rounds/offpage.py)."""
    return list((turn.draft.extra.get('offpage') or {}).get('cutaways') or [])


def scene_for(connection, turn, line: story.Telling | None) -> str:
    """The scene as today's narrator is given it: the place, its shop and the year; what code settled for the player's
    line (the road, the counter, the fight, treatment, finds); and the cutaways to place."""
    view = story.scene(connection, story_clock.now(connection, turn.database.clock))
    parts = [story.place_prompt(connection, view, story.shop_view(connection, view))]
    if playing(turn) and (who := story.persona_text(connection)[0]):
        parts.append(f"The user's character:\n{fence('persona', who)}")
    parts.append(story.settled_text(connection, line) if line is not None else beats.cutaway_text(cutaways(turn)))
    return '\n\n'.join(part for part in parts if part)


def round_system(connection, turn, data: dict) -> prompt_layout.Tiered:
    """The Writer's system prompt, which holds only what stays put from round to round, so it and the story so far
    after it can be cached (adventure/prompt_layout.py): its rules, then the story's settings. What it may know this
    round goes after the story so far, in the closing message (`asked`)."""
    chosen = story.narration_format(connection)
    craft = narration_prompt.craft_for(config(connection).get('context_tokens'),
                                       prompt_library.text(connection, 'narrator-craft'))
    rules = (prompt_library.text(connection, 'round-writer'), craft, fence_rule())
    settings = (f'Length: {narration_prompt.LENGTHS[chosen.length]} per round.',
                tone.narration(story.intensity(connection, data)).text(), rules_text(connection, turn, data),
                focus(connection, turn))
    return prompt_layout.stable(joined(rules), joined(settings))


def joined(layers) -> str:
    return '\n\n'.join(layer.strip() for layer in layers if layer and layer.strip())


WRITE = 'Write the round, ending at the stop point.'


def asked(known: str) -> dict:
    """The closing message: what the Writer may know this round, then the ask. It comes after the story so far, so a
    new round changes only the end of the request."""
    return {'role': 'user', 'content': joined((known, WRITE))}


def history(connection, turn) -> list[dict]:
    """The story so far as the reader saw it, before this turn, word for word as far as it fits. An Author or Watch
    turn's opening line holds a nudge or nothing, not the story, so it is left out."""
    where, values = timeline.visible(connection)
    away = {row['id'] for row in many(connection, f"SELECT id FROM story_messages WHERE {where} AND role='user' AND "
                                                  "mode IN ('author', 'watch')", values)}
    rows = [row for row in story.messages(connection) if row['seq'] < turn.point.seq and row['id'] not in away]
    return story.model_messages(rows, HISTORY_CHARS)


def inventions(text: str, canon: str) -> list[dict]:
    """New names in the post: capitalized words, or runs of them, that nothing the Writer was given contains (a single
    word opening a sentence is left alone). Each with the sentence that brought it in; kept unless the user strikes
    it (spec "Inventions")."""
    known, found = canon.lower(), {}
    prose = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
    for match in CAPITALIZED.finditer(prose):
        name = match[0]
        if (' ' not in name and OPENS_SENTENCE.search(prose[:match.start()])) or name.lower() in known:
            continue
        sentence = next((part.strip() for part in SENTENCE.findall(prose) if name in part), name)
        found.setdefault(name, {'name': name, 'text': sentence})
    return list(found.values())


async def streamed(turn, system: str, messages: list[dict]) -> str:
    """The post as it is written, each piece sent to the screen as it comes; out-of-character sentences dropped."""
    app, guard, pieces = turn.app, in_character.Guard(), []

    async def sent(piece: str):
        if piece:
            pieces.append(piece)
            if turn.on_text is not None:
                await turn.on_text(piece)
    with app.database.connect() as connection:
        settings = config(connection)
    usage = {}
    async with app.scheduler.reserve(settings, CONVERSATION):
        async for chunk in app.provider.stream(settings, key_for(app.vault, settings), system, messages):
            usage |= chunk.usage or {}
            await sent(guard.feed(chunk.text))
    await sent(guard.flush())
    pace.count_cache(turn.draft.extra, usage)
    return ''.join(pieces).strip()


async def write(turn):
    """Writing: the round rendered from its result, from the mode's point of view, streamed. A player's line with no
    agents in the campaign is told as today (adventure/rounds/telling.py). With agents, the line's packet is still
    built, since Commit's writes for it read the packet; the round Writer writes the post in place of today's
    narrator, and the line's reply is saved with it (telling.py 'story'). The post is the reply to the line the turn
    opened on (adventure/rounds/play.py), so a turn begun without one writes nothing."""
    line = await telling.telling_of(turn)
    if line is not None and (not turn.snapshot.agents() or turn.draft.result is None):
        await telling.write(turn)
        return
    if turn.draft.post or turn.draft.result is None or not turn.row.get('anchor_id'):
        return  # written already (a turn picked up again), or nothing to answer: no result, or no line to reply to
    if line is not None:
        line.meanwhile = cutaways(turn)
        story.packed(line)
    await turn.emit({'stage': 'writing'})
    with turn.database.connect() as connection:
        data = story.city_data(connection, story.scene_row(connection)['city_id'])
        known = context_for(connection, turn, scene_for(connection, turn, line))
        system, messages = round_system(connection, turn, data), history(connection, turn)
    messages = [*messages, asked(known)]
    turn.draft.post = await streamed(turn, system, messages)
    canon = naming.allowed_words(data, known, *(message['content'] for message in messages))
    turn.draft.extra.setdefault(KEY, {})['inventions'] = inventions(turn.draft.post, canon)


def context_for(connection, turn, scene: str) -> str:
    from adventure.rounds import context, directing
    return context.writer(connection, turn.snapshot, turn.draft, scene=scene, signs=directing.signs(turn))


def committed(connection, turn):
    """A round with no player's line (Author, Watch, or Next in Play): its post saved as the narrator's reply to the
    turn's opening line, in Commit's transaction. A player's line keeps its reply through today's telling."""
    post, anchor = turn.draft.post, turn.row.get('anchor_id')
    if not post or not anchor or telling.reply_of(turn) or telling.line_of(turn) is not None:
        return
    reply = story.add(connection, turn.database.now(), 'narrator', post, story.scene_row(connection),
                      reply_to=anchor)
    turn.draft.extra.setdefault(KEY, {})['reply'] = reply


engine.register(State.WRITING, 'write', write)
engine.on_commit('writer', committed)
