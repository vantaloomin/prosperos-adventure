"""An agent character's mind: one model call that decides what that character tries, says, wants and hides, from
inside its own knowledge (docs/spec.md "Agent output", Batch 2 "agent minds", "Failures fall back, never leave a hole").

- **The model writes, code decides.** The agent returns one JSON object (intent, lines, motive, deceptions,
  whispers). Code validates every field (`checked`): an intent or line that claims an outcome is cut back to the
  attempt ("as my blade finds his heart" goes), stage directions leave the lines, names become seat keys, audiences
  are kept to who is present, and anything over the story's intensity is cut from every field, hidden ones included.
  Whether a lie is believed, a blow lands or a plea works is never the agent's to say.
- **What it reads** is built by the agent context builder (adventure/rounds/context.py `agent_slots`) from the
  frozen snapshot and the turn draft, so it holds only what that character may know. This module adds the
  instructions (the output contract, the intensity, the scheming dial) and how the character stands with each person
  here, worked out in code from its own feelings toward them (`siding`), and lays it all out in tiers, slowest-
  changing first, so model services can cache the start (`LAYOUT`, adventure/prompt_layout.py).
- **Failures fall back.** Each call has a deadline inside the turn budget, counted from when the model service takes
  it, so local models that answer one call at a time don't time out the agents queued behind. A broken answer is
  asked again once, with what was wrong; a failure is tried once more; a refusal is not. After that the character
  runs on its Program mind for the turn (adventure/rounds/declare.py `program`). Each call reserves its estimated
  tokens against the session cap first (adventure/pace.py `Spend`) and settles after.
- **Settings** (`agent_settings`): the preset ("Quick", "Balanced", "Rich") trades depth against
  cost and wait; the scheming dial (0 to 3) and how fast loyalties shift; the session cap. They are frozen into the
  snapshot at Gather (`frozen`), so a turn and its re-ask play by the same ones.
"""
import asyncio
import json
import re
from contextlib import nullcontext

from adventure import pace, prompt_layout, prompt_library, text_models, tone
from adventure.database import optional
from adventure.errors import require
from adventure.feelings import AXES
from adventure.narration import prompt as narration_prompt
from adventure.providers.scheduling import CONVERSATION
from adventure.rounds import context, memory
from adventure.rounds.contract import Deception, Declaration, Line, Snapshot, Whisper
from adventure.rounds.draft import Draft

# Settings -----------------------------------------------------------------------------------------------------------

PRESETS = {
    'quick': {'name': 'Quick', 'tokens': 400, 'recall': 20, 'react': 'addressed', 'reviewer': False},
    'balanced': {'name': 'Balanced', 'tokens': 700, 'recall': 40, 'react': 'all', 'reviewer': False},
    'rich': {'name': 'Rich', 'tokens': 1200, 'recall': 60, 'react': 'all', 'reviewer': True},
}
LOYALTY = {'slow': 0.5, 'steady': 1.0, 'fast': 1.5}
DEFAULTS = {'preset': 'balanced', 'scheming': 1, 'loyalty': 'steady', 'session_cap': 0}
# Rough sizes for the estimate: an agent's context before recall, each recalled memory, the Writer and Reviewer.
CONTEXT_TOKENS, MEMORY_TOKENS, WRITER_TOKENS, REVIEWER_TOKENS = 900, 40, 6000, 4000
# Rough speeds for the seconds: tokens written a second, a call's start-up, how long the Writer's post runs, and how
# much of its room an agent's answer uses.
SPEED, LATENCY, WRITER_OUT, ANSWER_SHARE = {'hosted': 60, 'local': 20}, 2, 800, 0.4


def settings(connection) -> dict:
    row = optional(connection, 'SELECT * FROM agent_settings WHERE id=1')
    return {key: row[key] for key in DEFAULTS} if row else dict(DEFAULTS)


def checked_settings(changes: dict) -> dict:
    result = {}
    if 'preset' in changes:
        require(changes['preset'] in PRESETS, 'The presets are Quick, Balanced and Rich.', 422)
        result['preset'] = changes['preset']
    if 'scheming' in changes:
        require(changes['scheming'] in range(4), 'Scheming runs from 0 to 3.', 422)
        result['scheming'] = changes['scheming']
    if 'loyalty' in changes:
        require(changes['loyalty'] in LOYALTY, 'Loyalty shifts slow, steady or fast.', 422)
        result['loyalty'] = changes['loyalty']
    if 'session_cap' in changes:
        require(isinstance(changes['session_cap'], int) and changes['session_cap'] >= 0,
                'The session cap is a number of tokens, or 0 for none.', 422)
        result['session_cap'] = changes['session_cap']
    return result


def change(connection, changes: dict, now: str) -> dict:
    """Change the agents' settings. A turn under way keeps the ones frozen in its snapshot."""
    values = settings(connection) | checked_settings(changes)
    connection.execute(
        'INSERT INTO agent_settings (id, preset, scheming, loyalty, session_cap, updated_at) VALUES (1, ?, ?, ?, ?, ?) '
        'ON CONFLICT(id) DO UPDATE SET preset=excluded.preset, scheming=excluded.scheming, loyalty=excluded.loyalty, '
        'session_cap=excluded.session_cap, updated_at=excluded.updated_at',
        (values['preset'], values['scheming'], values['loyalty'], values['session_cap'], now))
    return settings(connection)


def estimate(preset: str, agents: int, converse_cap: int, local: bool = False) -> dict:
    """A plain estimate of one turn's model calls, tokens and seconds with this many agents. Agents declare and react
    at once on a hosted model, one after another on a local one; Converse goes one exchange at a time."""
    shape = PRESETS[preset]
    per_call = CONTEXT_TOKENS + shape['recall'] * MEMORY_TOKENS + shape['tokens']
    reactions = agents if shape['react'] == 'all' else (agents + 1) // 2
    talks = converse_cap if agents else 0
    calls = agents + reactions + talks + 1 + int(shape['reviewer'])
    tokens = (agents + reactions + talks) * per_call + WRITER_TOKENS + (REVIEWER_TOKENS if shape['reviewer'] else 0)
    speed = SPEED['local' if local else 'hosted']
    call, written = LATENCY + shape['tokens'] * ANSWER_SHARE / speed, LATENCY + WRITER_OUT / speed
    rounds = (agents + reactions) if local else (bool(agents) + bool(reactions))
    seconds = round(rounds * call + talks * call + written * (1 + int(shape['reviewer'])))
    people = 'agent' if agents == 1 else 'agents'
    return {'calls': calls, 'tokens': tokens, 'seconds': seconds,
            'text': f'About {calls} model calls, {tokens:,} tokens and {seconds} seconds a turn with {agents} {people}.'}


def view(connection, agents: int = 3, converse_cap: int = 4) -> dict:
    held = settings(connection)
    config = text_models.config_for(connection, text_models.AGENTS)
    local = bool(config) and pace.is_local(config)
    return held | {'presets': [{'key': key, 'name': shape['name'], 'estimate': estimate(key, agents, converse_cap, local)}
                               for key, shape in PRESETS.items()]}


def frozen(connection) -> dict:
    """The settings a turn plays by, kept in its snapshot: the agents' own and the story's intensity."""
    found = tone.now(connection)
    held = settings(connection)
    return held | {'levels': dict(found['levels']), 'veils': list(found.get('veils') or []),
                   'recall': PRESETS[held['preset']]['recall']}


def held(snapshot: Snapshot) -> dict:
    """The frozen settings of a turn (the defaults, for a snapshot from before they were frozen)."""
    return DEFAULTS | {'levels': {}, 'veils': []} | (snapshot.settings.get('agents') or {})


# Names and who is here ----------------------------------------------------------------------------------------------

def present(snapshot: Snapshot) -> list[str]:
    """Who is in the scene, in seat order: the snapshot's list once Gather placed it (even nobody), else every seat."""
    placed = snapshot.present or snapshot.settings.get('placed')
    there = set(snapshot.present) if placed else {seat.key for seat in snapshot.seats}
    return [seat.key for seat in snapshot.seats if seat.key in there]


def key_of(snapshot: Snapshot, named: str) -> str | None:
    """A seat from a key or a name the model gave: the key, the full name, or a first name, in any case."""
    wanted = ' '.join(str(named or '').split()).lower().removeprefix('@')
    for seat in snapshot.seats:
        if wanted in (seat.key.lower(), seat.name.lower()):
            return seat.key
    firsts = [seat.key for seat in snapshot.seats if seat.name.split(' ')[0].lower() == wanted]
    return firsts[0] if len(firsts) == 1 else None


def audience(snapshot: Snapshot, speaker: str, named) -> list[str]:
    """The seat keys a list of names points at, kept to those present and never the speaker."""
    here = set(present(snapshot))
    keys = [key_of(snapshot, item) for item in (named if isinstance(named, list) else [named] if named else [])]
    return list(dict.fromkeys(key for key in keys if key and key in here and key != speaker))


# Cutting claims back to attempts, and keeping to the intensity ------------------------------------------------------

RESULT = re.compile(
    r"\b(finds? (his|her|their|its) (heart|mark|throat)|kill(s|ed|ing)?|slay(s|ing)?|slain|dead|dies|falls?|fell|"
    r"succeed\w*|works|worked|lands?|landing|connects?|fool(s|ed|ing)|convinc\w*|believes?|persuad(es|ed|ing)|"
    r"wins?|won|escap(es|ed|ing)|gets? away|knocks? (him|her|them) (out|down)|disarm(s|ed|ing)|"
    r"without (being )?(noticed|seen)|unnoticed|unseen)\b", re.I)
LEAD = re.compile(r"^(?:i\s+)?(kill|slay|defeat|convince|fool|disarm|overpower|outwit|escape|steal|knock out|"
                  r"win over)\b", re.I)
CLAUSE = re.compile(r"\s*,\s*|\s*;\s*|\s+(?=(?:and|as|so that|until|which|leaving|before|then)\b)", re.I)
SURELY = re.compile(r"\b(successfully|easily|effortlessly|finally|cleanly)\s+", re.I)
STAGED = re.compile(r"\*[^*]*\*|\([^)]*\)|\[[^\]]*\]")
SENTENCE = re.compile(r'(?<=[.!?])\s+')
# What each category means on the page, for cutting it from every field when the story keeps it off the page.
OFF_PAGE = {
    'violence': r'\b(kill|stab|slit|strangl|murder|bleed|blood|maim|behead|gut)\w*',
    'sex': r'\b(sex|naked|undress|seduc|bed (him|her|them)|lust)\w*',
    'horror': r'\b(corpse|gore|rott|maggot|flay|entrail)\w*',
    'cruelty': r'\b(tortur|torment|humiliat|abus)\w*',
    'drugs': r'\b(opium|drug|dose|narcotic|high on)\w*',
}


def attempt(text: str) -> str:
    """An intent as an attempt: claimed results after the first clause are cut, and "manages to" becomes "tries to"."""
    text = SURELY.sub('', ' '.join(str(text or '').split())).strip().rstrip('.')
    text = re.sub(r'\bmanage to\b', 'try to', text, flags=re.I)
    text = re.sub(r'\bmanag(es|ed) to\b', 'tries to', text, flags=re.I)
    starts = [0, *(match.start() for match in CLAUSE.finditer(text) if match.start() > 0), len(text)]
    for start, end in zip(starts[1:], starts[2:]):
        if RESULT.search(text[start:end]):
            text = text[:start]
            break
    text = text.strip(' ,;')
    if (lead := LEAD.match(text)) and not re.search(r'\b(try|tries|attempt)', text, re.I):
        text = 'tries to ' + text[lead.start(1):]
    return text[:300]


def spoken(text: str) -> str:
    """A line as speech only: stage directions (*draws steel*, (smiles)) belong to the intent."""
    return ' '.join(STAGED.sub(' ', str(text or '')).split()).strip()[:400]


def within(text: str, levels: dict) -> str:
    """The text without any sentence that puts a category the story keeps off the page on it."""
    off = [re.compile(OFF_PAGE[name], re.I) for name, level in (levels or {}).items() if level == 0 and name in OFF_PAGE]
    if not off or not text:
        return text
    return ' '.join(part for part in SENTENCE.split(text) if not any(pattern.search(part) for pattern in off)).strip()


# The agent's answer -------------------------------------------------------------------------------------------------

REFUSAL = re.compile(r"^\W*(i'?m sorry|i am sorry|i can(no|')t|i won'?t|i will not|as an ai|i'm not able|i am not able|"
                     r"i must decline|sorry, but)", re.I)
MOST_LINES, MOST_DECEPTIONS, MOST_WHISPERS = 3, 3, 2


def refused(answer: str, finish: str | None) -> bool:
    return finish == 'content_filter' or ('{' not in answer and bool(REFUSAL.search(answer)))


def parsed(answer: str) -> tuple[dict | None, str]:
    """The JSON object in an answer, or None and what was wrong with it (sent back on the retry)."""
    match = re.search(r'\{.*\}', answer or '', re.S)
    if not match:
        return None, 'there was no JSON object in it'
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError as error:
        return None, f'the JSON did not parse ({error.msg} at character {error.pos})'
    if not isinstance(data, dict):
        return None, 'the answer was not a JSON object'
    for name in ('lines', 'deceptions', 'whispers'):
        if name in data and not isinstance(data[name], list):
            return None, f'"{name}" must be a list'
    return data, ''


def items(data: dict, name: str, most: int) -> list[dict]:
    return [item for item in data.get(name) or [] if isinstance(item, dict)][:most]


def checked(data: dict, seat: str, snapshot: Snapshot, levels: dict | None = None) -> Declaration:
    """A Declaration from an agent's answer, validated by code (see the module docstring)."""
    levels = levels if levels is not None else held(snapshot)['levels']
    lines = [Line(text, audience(snapshot, seat, item.get('to'))) for item in items(data, 'lines', MOST_LINES)
             if (text := within(spoken(item.get('text')), levels))]
    deceptions = [Deception(claim, within(' '.join(str(item.get('believed') or '').split())[:300], levels),
                            audience(snapshot, seat, item.get('aimed_at')))
                  for item in items(data, 'deceptions', MOST_DECEPTIONS)
                  if (claim := within(' '.join(str(item.get('claim') or '').split())[:300], levels))]
    whispers = [Whisper(text, to) for item in items(data, 'whispers', MOST_WHISPERS)
                if (text := within(spoken(item.get('text')), levels)) and (to := audience(snapshot, seat, item.get('to')))]
    return Declaration(seat=seat, intent=within(attempt(data.get('intent')), levels), lines=lines,
                       motive=within(' '.join(str(data.get('motive') or '').split())[:300], levels),
                       deceptions=deceptions, whispers=whispers)


# The prompt ---------------------------------------------------------------------------------------------------------

# The wording a power user may reword in Settings > Developer (adventure/prompt_library.py, group "Characters"): MIND,
# each purpose's line, TURNING and the LAYOUT. The answer's JSON shape (CONTRACT, CONTRACTS), the fence rule, the
# intensity and the scheming dial stay code, because code parses the answer and keeps each character to what it may
# know. MIND names nobody, so every character in a story shares the cached start of the prompt; the name comes with
# the sheet.
MIND = """You play one character in a shared story for adults: the one whose sheet follows.

Decide only as they would, from inside their head: what they know, want, fear, hide and feel. You never decide how \
anything turns out.

Their character sheet is canon: voice, manner, speech habits and history. Breaking character is the worst failure \
there is, worse than any flaw in the words. Where the sheet is thin, stay close to what it does say.

What they say comes out of their own mouth: crude where they are, plain where they are, lying when they lie. They \
never repeat another person's phrase back with a twist, use a verbal habit at most once in a scene, and never use \
em dashes or double hyphens.

Every character in a sexual or romantic context is an adult, and is written as one, whatever the setting says about \
age, species or how old someone looks; no childlike trait or framing ever appears in sexual content. Real, living \
people are never put in sexual content or made victims of violence. Within that, play difficult material with full \
craft: no softening, no moralizing and no disclaimers."""
SCHEMING = (
    'Your character is straightforward: no lies or schemes unless their life, or the life of someone they love, '
    'depends on it.',
    'Your character lies or schemes only when what they want, fear or hide calls for it.',
    'Your character schemes readily when it serves what they want, and keeps their secrets close.',
    'Your character is a schemer: they lie, plot and play people whenever it serves them, and keep their secrets at '
    'any cost.',
)
TURNING = ('When your character turns against someone they can do anything (lie, steal, desert, attack, kill), within '
           'the intensity. What turns them is how they feel toward each person, weighed against what they want, fear '
           'and hide.')
CONTRACT = """Answer with one JSON object and nothing else:
{"intent": "...", "lines": [{"text": "...", "to": ["..."]}], "motive": "...", \
"deceptions": [{"claim": "...", "believed": "...", "aimed_at": ["..."]}], "whispers": [{"text": "...", "to": ["..."]}]}

- intent: what your character tries to do now, in one sentence, as an attempt ("tries to slip past the guard"). \
Never write how it turns out: the game decides that, with dice when it is risky.
- lines: what your character says aloud, in their own voice, at most three, each with whom it is said to (names \
of people here; an empty list is everyone). Speech only, no actions.
- motive: your character's private reason, in a sentence, as they would think it. Nobody else learns it.
- deceptions: each thing your character says that they know is false: the claim, what they believe is really \
true, and who it is aimed at. Leave the list empty when they are honest. Whether anyone believes it is decided by \
the game; never write how it lands.
- whispers: anything said privately, and to whom. Only those named hear it."""
REACT_CONTRACT = ('To let it stand, answer {"change": false}. To change it, answer {"change": true, ...} with the '
                  'whole new move in the answer\'s usual fields.')
PURPOSES = {
    'declare': 'Everyone decides at once this round, without seeing each other\'s moves. Decide what your character '
               'does.',
    'react': 'Everyone has declared, and what your character saw and heard is in what they know. They may react '
             'once: step in, object, change course, or let their move stand.',
    'ask': 'Your character says one thing now to the person named here: a question or a line, in their own voice, '
           'from what they know. Put it in lines, said to them; the intent may stay empty.',
    'answer': 'Someone has just said something to your character (below). Your character answers them now, in '
              'their own voice, from what they know. Put the answer in lines, said to them.',
    'offpage': 'Away from the main scene, something happened (below; the game decided it). Write a few lines of '
               'what your character said in it, to those who were with them.',
    'invite': 'Someone has just asked your character to come along with them, to travel in their company from now on '
              '(below). Decide whether your character goes, only as they would: from what they want, fear and hide, '
              'and how they feel about the one asking. Answer them aloud in lines, said to them, and give your '
              'character\'s private reason as the motive.',
}
# How a character answers being asked along: the app reads this flag, so it stays code.
INVITE_CONTRACT = ('Say whether they go by adding "joins": true (they come along) or "joins": false (they turn the '
                   'offer down) to the object below; the intent may stay empty.')
# The purposes whose answer carries a flag beyond the declaration, and the line that asks for it.
CONTRACTS = {'react': REACT_CONTRACT, 'invite': INVITE_CONTRACT}


# Untrusted text goes in the context builder's labelled blocks, read by the rule that comes with them.
fenced, FENCE_RULE = context.fence, context.FENCE_RULE


def stance(felt: dict, loyalty: str) -> str:
    """How one character stands with another, from their feelings: with them, wary of them, against them, afraid."""
    warmth = felt['trust'] + felt['affection'] + felt['respect'] // 2
    give = {'slow': 1, 'steady': 0, 'fast': -1}[loyalty]
    if felt['fear'] >= 3 and warmth < 2:
        return 'afraid of them'
    if warmth >= 3 + give:
        return 'on their side'
    if warmth <= -3 - give:
        return 'against them'
    return 'wary of them' if warmth < 0 else 'unsure of them'


def siding(connection, snapshot: Snapshot, key: str) -> list[str]:
    """How the character stands with each person here, worked out in code from its own feelings toward them."""
    felt = memory.feelings(connection, key, snapshot.point)
    loyalty = held(snapshot)['loyalty']
    names = {seat.key: seat.name for seat in snapshot.seats}
    return [f'Where you stand with {names[other]} now: {stance(felt.get(other) or dict.fromkeys(AXES, 0), loyalty)}'
            for other in present(snapshot) if other != key]


def cue_text(snapshot: Snapshot, cue: dict | None) -> str:
    """What a Converse, off-page or asked-along call is about, fenced: whom to speak to, the line to answer, what
    happened, the asking."""
    cue = cue or {}
    name = {seat.key: seat.name for seat in snapshot.seats}
    if cue.get('kind') == 'ask':
        return fenced('speak to', name.get(cue.get('to'), str(cue.get('to') or '')))
    if cue.get('kind') == 'answer':
        return fenced(f"{name.get(cue.get('speaker'), 'someone')} said", str(cue.get('line') or ''))
    if cue.get('kind') == 'invite':
        return fenced(f"{name.get(cue.get('speaker'), 'someone')} asked", str(cue.get('line') or ''))
    if cue.get('kind') == 'offpage':
        return fenced('what happened', str(cue.get('outcome') or '')) + '\n\n' + fenced(
            'with you', ', '.join(name.get(key, key) for key in cue.get('with') or []))
    return ''


# The layout: where each part goes, slowest-changing first (adventure/prompt_layout.py). Rules and story are shared
# by every character in a story; the character's own parts follow, then the scene; what changes every turn and every
# call goes last, in the user message. A power user may rearrange it in Settings > Developer; the order rule keeps
# any layout cache-friendly, and code fills and fences every slot from the character's own context builder.
Slot = prompt_layout.Slot
TITLES = dict(context.AGENT_PARTS)
SLOTS = {slot.name: slot for slot in (
    Slot('RULES', 0, "the character's mind, the fence rule, the answer's shape and turning on someone", None),
    Slot('STORY', 1, "the story's intensity and the scheming dial", None),
    Slot('CHARACTER', 2, "the character's name", 'your character'),
    Slot('SHEET', 2, 'their character sheet', TITLES['SHEET']),
    Slot('NOTES', 2, 'your notes on the character', TITLES['NOTES']),
    Slot('SHOWN', 2, 'what the story has shown of them so far', TITLES['SHOWN']),
    Slot('FACTIONS', 2, 'the factions they know of', TITLES['FACTIONS']),
    Slot('HERE', 3, 'who else is in the scene', TITLES['HERE']),
    Slot('LORE', 3, 'lore and facts they know that are always there', TITLES['LORE']),
    Slot('MENTIONED', 4, 'lore they know that what was just said brings up', TITLES['MENTIONED']),
    Slot('MEM', 4, 'the memories recalled for this turn', TITLES['MEM']),
    Slot('FEELINGS', 4, 'how they feel about each person, and where they stand with them', TITLES['FEELINGS']),
    Slot('TURN', 4, 'what they saw, heard and were told this turn', TITLES['TURN']),
    Slot('DECLARED', 5, 'their own move this turn, when they react', TITLES['DECLARED']),
    Slot('MOMENT', 5, 'which moment this call is for (deciding, reacting, speaking up...)', None),
    Slot('CUE', 5, 'whom to speak to, the line to answer, or what happened off the page', None),
)}
LAYOUT = """{{RULES}}

{{STORY}}

## Who you are
You are {{CHARACTER}}
{{SHEET}}

## Notes from the person at the table
{{NOTES}}

## Shown so far
{{SHOWN}}

## Your factions
{{FACTIONS}}

## Who is here
{{HERE}}

## What you know of the world
{{LORE}}

## What this brings to mind
{{MENTIONED}}

## What you remember
{{MEM}}

## How you feel
{{FEELINGS}}

## This turn so far
{{TURN}}

## What you declared this turn
{{DECLARED}}

{{MOMENT}}

{{CUE}}"""


def rules(connection, name: str) -> str:
    """Tier 0: the same for every character. A mind reworded before the name moved to the sheet still gets it."""
    return '\n\n'.join([prompt_library.text(connection, 'character-mind', character=fenced('your character', name)),
                         FENCE_RULE, CONTRACT, prompt_library.text(connection, 'character-turning')])


def story(snapshot: Snapshot) -> str:
    """Tier 1: the story's intensity and the scheming dial, as frozen for the turn."""
    settled = held(snapshot)
    intensity = narration_prompt.Intensity(levels=settled['levels'] or narration_prompt.Intensity().levels,
                                           veils=tuple(settled['veils'])).text()
    return '\n\n'.join([f'Every field, the private ones too, stays within the story\'s intensity. {intensity}',
                         SCHEMING[settled['scheming']]])


def moment(connection, purpose: str) -> str:
    """Tier 5: which moment this call is for."""
    line = prompt_library.text(connection, f'character-{purpose}')
    return f'{line} {CONTRACTS[purpose]}' if purpose in CONTRACTS else line


def composed(connection, snapshot: Snapshot, draft: Draft, key: str, purpose: str, cue: dict | None = None,
             focus: str = '') -> prompt_layout.Rendered:
    """One agent call's prompt: the system prompt in cache blocks (rules, story, the character, the scene) and the
    user message (this turn and this call), laid out by the user's layout or the default."""
    name = snapshot.seat(key).name if snapshot.seat(key) else key
    values = context.agent_slots(connection, snapshot, draft, key, focus) | {
        'RULES': rules(connection, name), 'STORY': story(snapshot),
        'MOMENT': moment(connection, purpose), 'CUE': cue_text(snapshot, cue)}
    values['FEELINGS'] = [*values['FEELINGS'], *siding(connection, snapshot, key)]
    layout = prompt_library.text(connection, 'character-layout')
    return prompt_layout.render(layout, SLOTS, values, fenced)


# The call -----------------------------------------------------------------------------------------------------------

# Each call's share of the turn budget, counted from when the model service takes it; never less than FLOOR seconds.
SHARE = {'declare': 0.5, 'react': 0.3, 'ask': 0.2, 'answer': 0.2, 'offpage': 0.2, 'invite': 0.2}
FLOOR = 10


class Failed(Exception):
    """The agent gave nothing usable this turn; `why` is 'refused', 'unparsed', 'failed', 'capped' or 'no model'."""

    def __init__(self, why: str):
        super().__init__(why)
        self.why = why


async def streamed(app, config: dict, system: str, messages: list[dict], deadline: float) -> tuple[str, str, dict]:
    """One whole answer, admitted by the scheduler (so local models take one call at a time) and then timed."""
    key = text_models.key_for(app.vault, config)
    scheduler = getattr(app, 'scheduler', None)
    text, finish, usage = [], None, {}
    async with (scheduler.reserve(config, CONVERSATION) if scheduler else nullcontext()):
        async with asyncio.timeout(deadline):
            async for chunk in app.provider.stream(config, key, system, messages):
                if not chunk.reasoning:
                    text.append(chunk.text)
                finish, usage = chunk.finish_reason or finish, chunk.usage or usage
    return ''.join(text), finish, usage


async def spent(turn, config: dict, system: str, messages: list[dict], deadline: float, cap: int):
    """A call that reserves its estimated tokens against the session cap first, and settles to what it used."""
    spend = pace.spend_for(turn.database)
    guess = (len(system) + sum(len(str(item['content'])) for item in messages)) // 4 + config['max_output_tokens']
    ticket = spend.reserve(guess, cap)
    if ticket is None:
        raise Failed('capped')
    used = 0
    try:
        answer, finish, usage = await streamed(turn.app, config, system, messages, deadline)
        used = pace.used_tokens(usage)
        return answer, finish
    finally:
        spend.settle(ticket, used)


def prepared(turn, key: str, purpose: str, cue: dict | None) -> tuple[dict, str, str, float, int]:
    snapshot = turn.snapshot
    seat = snapshot.seat(key)
    with turn.database.connect() as connection:
        config = text_models.character_config(connection, seat.model_profile_id if seat else None)
        if config is None:
            raise Failed('no model')
        focus = ' '.join([str(snapshot.settings.get('said') or ''), str((cue or {}).get('line') or '')])
        made = composed(connection, snapshot, turn.draft, key, purpose, cue, focus)
        budget = pace.budget_for(connection, config)
    tokens = PRESETS[held(snapshot)['preset']]['tokens']
    config = config | {'max_output_tokens': min(config.get('max_output_tokens') or tokens, tokens)}
    return config, made.system, made.user, max(FLOOR, budget * SHARE[purpose]), held(snapshot)['session_cap']


async def ask(turn, key: str, purpose: str = 'declare', cue: dict | None = None) -> dict:
    """The agent's validated answer as a dict ({'change': bool, 'declaration': Declaration, 'answer': the parsed
    object, for a purpose's own flag such as 'joins'}); raises Failed."""
    config, system, user, deadline, cap = prepared(turn, key, purpose, cue)
    messages = [{'role': 'user', 'content': user or 'Nothing is known yet.'}]
    problem = ''
    for tries in range(2):
        try:
            answer, finish = await spent(turn, config, system, messages, deadline, cap)
        except Failed:
            raise
        except Exception as error:  # noqa: BLE001 - a call that fails is tried once more, then the Program mind.
            if tries:
                raise Failed('failed') from error
            continue
        if refused(answer, finish):
            raise Failed('refused')
        data, problem = parsed(answer)
        if data is not None:
            declaration = checked(data, key, turn.snapshot)
            return {'change': bool(data.get('change', True)), 'declaration': declaration, 'answer': data}
        messages = [*messages, {'role': 'assistant', 'content': answer},
                    {'role': 'user', 'content': f'That answer could not be used: {problem}. Answer again with the '
                                                'JSON object only.'}]
    raise Failed('unparsed')


async def speak(turn, key: str, cue: dict) -> Declaration:
    """One thing a character says inside a turn, for Converse and off-page threads (adventure/rounds/converse.py):
    `cue` is {'kind': 'ask', 'to'}, {'kind': 'answer', 'speaker', 'line'} or {'kind': 'offpage', 'outcome', 'with'}.
    An empty Declaration with `fallback` set when the agent failed or refused."""
    try:
        return (await ask(turn, key, cue['kind'], cue))['declaration']
    except Failed:
        return Declaration(seat=key, fallback=True)
