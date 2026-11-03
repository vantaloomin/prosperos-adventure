"""Prompt layouts: where live game content goes in a prompt, in an order model services can cache (docs/prompts.md
"Layouts and caching").

Claude, OpenAI, Gemini and llama.cpp all reuse the work of reading a prompt only for its unchanged start, so what
changes least goes first. Each piece of live content is a **slot** (`{{SHEET}}`, `{{MEM}}`, ...), and each slot
belongs to a **tier**, from slowest-changing to fastest:

| Tier | Changes when |
| --- | --- |
| 0 Rules | the app updates, or the user rewords a prompt |
| 1 Story | the story's settings change |
| 2 Character | the character's sheet or notes change |
| 3 Scene | a scene starts, or who is in it changes |
| 4 Turn | every turn |
| 5 Call | every call |

A layout is plain text with slots in it. It is refused when a slot comes before one from a slower tier, so no layout
can put something that changes every turn ahead of something that could stay cached. Tiers 0 to 3 make the system
prompt, sent as blocks that each end where a provider that takes cache marks should put one; tiers 4 and 5 make the
user message.

**A slot is a position, never a permission.** Code fills every slot from that reader's own context builder
(adventure/rounds/context.py), and each reader is offered only the slots its builder fills, so no layout can show a
character anything it may not know. Slot content that comes from outside code is always fenced by code, under a
label code chooses, whatever the words around it say. A slot left out of a layout is put back at the end of its
tier, so content never silently disappears.

A layout is read in paragraphs (split by blank lines). A paragraph whose slots are all empty this call is left out,
so a label written in the same paragraph as its slot goes with it. A paragraph with no slot stays with the tier of
the paragraph before it.
"""
import hashlib
import re
from dataclasses import dataclass

TIERS = ('rules', 'story', 'character', 'scene', 'turn', 'call')
CHANGES = ('only when the app updates or a prompt is reworded', "only when the story's settings change",
           "only when the character's sheet or notes change", 'when a scene starts', 'every turn', 'every call')
# Tiers below this go in the system prompt (cached); the rest go in the user message.
CACHED = 4
# Each of these tiers ends a block of the system prompt, where Claude gets a cache mark (it takes four a request,
# and a retry's conversation uses the fourth). Rules and story make one block: every character in a story shares it.
BREAKS = (1, 2, CACHED - 1)
SLOT = re.compile(r'\{\{(\w+)\}\}')
SINGLE = re.compile(r'(?<!\{)\{(\w+)\}(?!\})')
PARAGRAPH = re.compile(r'\n[ \t]*\n')


@dataclass(frozen=True)
class Slot:
    name: str
    tier: int
    help: str
    # The fence label code puts round this slot's content; None when code wrote all of it (an instruction) or fenced
    # it already (the cue).
    fence: str | None
    # The kind of fence, when the reader tells kinds apart (a character's own sheet is `who-you-are`); None for the
    # fence function's default.
    kind: str | None = None


SEPARATOR = '\n\n'


class Tiered(str):
    """A system prompt that knows its cache blocks. It is the whole prompt as a str for every caller; `blocks` are
    its pieces, each ending where a cache mark goes, and `cache_key` names the stable start that calls for the same
    character share (OpenAI's `prompt_cache_key`)."""
    blocks: tuple[str, ...]
    cache_key: str

    def __new__(cls, blocks, cache_key: str = ''):
        kept = tuple(block for block in blocks if block)
        made = super().__new__(cls, SEPARATOR.join(kept))
        made.blocks, made.cache_key = kept, cache_key
        return made


@dataclass(frozen=True)
class Rendered:
    system: Tiered
    user: str


def slots_in(text: str) -> list[str]:
    return SLOT.findall(text)


def mark(name: str) -> str:
    return '{{' + name + '}}'


def problems(text: str, slots: dict[str, Slot], reader: str) -> str | None:
    """Why a layout cannot be used, in words the user can act on, or None."""
    names = slots_in(text)
    marks = lambda keys: ', '.join(mark(key) for key in keys)  # noqa: E731
    single = sorted({name for name in SINGLE.findall(text) if name in slots})
    if single:
        return f'Use double braces for the slots: write {marks(single)}.'
    unknown = [name for name in dict.fromkeys(names) if name not in slots]
    if unknown:
        return (f'The app does not fill {marks(unknown)} for {reader}, so it would be sent as written. It can fill '
                f'{marks(slots)}.')
    twice = [name for name in dict.fromkeys(names) if names.count(name) > 1]
    if twice:
        return f'Use each slot once: {marks(twice)} appears more than once.'
    slowest = None
    for name in names:
        slot = slots[name]
        if slowest is not None and slot.tier < slowest.tier:
            return (f'{mark(name)} changes {CHANGES[slot.tier]}, but it comes after {mark(slowest.name)}, which '
                    f'changes {CHANGES[slowest.tier]}. Put {mark(name)} before {mark(slowest.name)}, so the part of '
                    'the prompt that stays the same comes first and can stay cached.')
        if slowest is None or slot.tier > slowest.tier:
            slowest = slot
    return None


def paragraphs(text: str) -> list[str]:
    return [part.strip('\n') for part in PARAGRAPH.split(text.strip()) if part.strip()]


def tiered(parts: list[str], slots: dict[str, Slot]) -> list[tuple[int, str]]:
    """Each paragraph with its tier: that of its fastest-changing slot, or the tier of the paragraph before it when it
    has no slot."""
    result, tier = [], 0
    for part in parts:
        found = [slots[name].tier for name in slots_in(part) if name in slots]
        tier = max(found) if found else tier
        result.append((tier, part))
    return result


def completed(parts: list[tuple[int, str]], slots: dict[str, Slot]) -> list[tuple[int, str]]:
    """The layout with every slot it left out put back at the end of that slot's tier."""
    present = {name for _, part in parts for name in slots_in(part)}
    result = list(parts)
    for slot in slots.values():
        if slot.name in present:
            continue
        at = next((index for index, (tier, _) in enumerate(result) if tier > slot.tier), len(result))
        result.insert(at, (slot.tier, mark(slot.name)))
    return result


def fence_text(slot: Slot, value, fence) -> str:
    lines = [str(line) for line in (value if isinstance(value, (list, tuple)) else [value]) if line]
    if not lines:
        return ''
    body = '\n'.join(lines)
    if slot.fence is None:
        return body
    return fence(slot.fence, body, slot.kind) if slot.kind else fence(slot.fence, body)


def render(layout: str, slots: dict[str, Slot], values: dict, fence) -> Rendered:
    """The prompt a layout makes with this call's values: each slot's content (a str or a list of lines) fenced by
    `fence(label, text)` unless code wrote it, empty paragraphs left out, tiers 0 to 3 as the system prompt's blocks
    and the rest as the user message."""
    filled = {name: fence_text(slot, values.get(name), fence) for name, slot in slots.items()}
    tiers: dict[int, list[str]] = {}
    for tier, part in completed(tiered(paragraphs(layout), slots), slots):
        names = [name for name in slots_in(part) if name in slots]
        if names and not any(filled[name] for name in names):
            continue
        text = SLOT.sub(lambda match: filled.get(match[1], match[0]), part).strip()
        if text:
            tiers.setdefault(tier, []).append(text)
    joined = {tier: SEPARATOR.join(parts) for tier, parts in tiers.items()}
    blocks, start = [], 0
    for end in BREAKS:
        blocks.append(SEPARATOR.join(joined[tier] for tier in range(start, end + 1) if tier in joined))
        start = end + 1
    stable = SEPARATOR.join(joined[tier] for tier in range(3) if tier in joined)
    key = 'prospero-' + hashlib.sha256(stable.encode()).hexdigest()[:24] if stable else ''
    user = SEPARATOR.join(joined[tier] for tier in range(CACHED, len(TIERS)) if tier in joined)
    return Rendered(Tiered(blocks, key), user)


def described(slots: dict[str, Slot]) -> list[dict]:
    """The slots as Settings lists them, slowest-changing first."""
    return [{'name': slot.name, 'tier': slot.tier, 'tier_name': TIERS[slot.tier], 'help': slot.help}
            for slot in sorted(slots.values(), key=lambda slot: slot.tier)]
