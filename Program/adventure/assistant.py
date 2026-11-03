"""The Sidebar Assistant: an out-of-story chat beside the app, after the sidecar in Prospero's Companion
(companion/sidecar.py), which came from the Collaborator in Prospero's Study (docs/assistant.md).

It sees the story (the scene, the recent lines, the cast met, the journal, the lore and the author's note) but is never
part of it: what is said in the sidebar is not stored, never reaches the narrator and never becomes a fact. It can
answer, explain and suggest, and it proposes changes the user applies one by one, each through the app's own path:

- the story's author's note (adventure/authors_note.py), switched on when applied;
- a narration in new words (adventure/story.py `replaced`), which Switch wording undoes;
- a journal fact added or corrected (adventure/record.py);
- a lore entry of the user's own (adventure/lore.py `add_entry`).

While the GM view is on (the Table's `gm_view`) it also sees what is behind the story, and may propose GM edits:
how someone feels toward the character (adventure/gm.py), and the director's planned beats, to cut, bring back or add
(adventure/plotting.py). With the GM view off it is shown none of that: hidden facts, GM-only lore, feelings and arcs
stay out of its context, so it cannot leak them, and GM edits are refused here as well as on their own routes.

The model only proposes. Every proposal is checked here against the context it was shown: it may only name lines,
facts, people, arcs and beats it was given, by the short references it was given. Nothing is applied by this module.
"""
from adventure import authors_note, feelings, gm, lore, plotting, record, story, story_clock, tiers
from adventure.database import decode, many, optional
from adventure.errors import DomainError
from adventure.text_models import config_for

JOB = 'assistant'
RECENT_LINES = 30
LINE_CHARS = 1500
JOURNAL_LIMIT = 120
LORE_LIMIT = 80
LORE_CHARS = 500
REPLY_CHARS = 3000
NARRATION_CHARS = 20000
CHAT = 'story'
VIEW_NAMES = {'story': 'the story', 'settings': 'Settings', 'worlds': 'Worlds'}

SYSTEM = """You are the Sidebar Assistant in Adventure, an app where a narrator model tells the user's story as a \
tabletop roleplaying game. You sit beside the story, outside it: the user talks to you about the story, not to the \
narrator or to anyone in it. What you say here never reaches the narrator and never becomes part of the story.

You can see the scene, the recent story, the people met, the journal, the lore and the author's note below. Use them to:
- answer questions and explain: what happened, who someone is, why the narrator did something, what is unresolved;
- suggest: where the story could go, a sharper passage, a missing detail;
- change things for the user when they ask: the author's note, the wording of one of the narrator's passages, a \
journal fact (add one, or correct one), or a new lore entry;
- steer the story with the author's note: a short note of the user's sent with every narration while it is on, which \
the narrator follows but never shows. When the user wants to steer the story for a while (a mood, a pace, something \
to avoid), offer to write it as an author's note.
{gm_tools}
The user reviews every change before it is used, so propose a change only when they ask for one or clearly want one. \
Keep what they have written unless they ask you to change it. You cannot change the user's own lines, the dice or \
what the rules decided; a passage in new words must keep what happened in it.

{view}

The scene:
{scene}

The recent story, oldest first ([m…] are the lines; only the narrator's can be reworded):
{lines}

People the character has met:
{people}

The journal (what the character knows{journal_note}):
{journal}

Lore the narrator may read:
{lore}

The story's author's note:
{note}
{gm_context}
Reply with one JSON object and nothing else: no Markdown fence, no commentary.
{{"reply": "what you say to the user, plain and brief", "changes": [ ... ]}}
Each change is one of:
- {{"kind": "authors_note", "text": "the whole note, a few plain sentences that steer the coming narration"}}
- {{"kind": "narration", "ref": "m7", "text": "the whole new wording of that narrator's passage"}}
- {{"kind": "journal_add", "subject": "who or what it is about, in a few words", "text": "the fact in one sentence"}}
- {{"kind": "journal_fix", "ref": "k3", "text": "the corrected fact"}}
- {{"kind": "lore_add", "title": "a short title", "text": "the lore", "keywords": ["words that bring it in"], \
"always": false{secret_field}}}{gm_kinds}
Use only the references shown above. Use [] for "changes" when nothing should change, and say in "reply" what each \
change does."""

GM_TOOLS = """- with the GM view on, make GM edits: how someone met feels toward the character, and the director's \
planned beats for each arc (cut one, bring one back, or add one of the user's own).
"""
GM_KINDS = """
- {"kind": "feelings", "ref": "p2", "trust": 2} with any of trust, affection, respect (-5 to 5), fear, desire (0 to 5)
- {"kind": "beat_cut", "ref": "b4", "cut": true} (false brings a cut beat back)
- {"kind": "beat_add", "ref": "a1", "text": "one sentence: something the world could do next in that arc"}"""
GM_CONTEXT = """
Behind the story (the GM view is on: the user sees all of this, the character does not):
How the people met feel toward the character:
{feelings}

The director's arcs, each at its stage with its hidden truth, and its planned beats:
{arcs}
"""
RETRY = 'Your answer could not be used: {reason} Answer again with the one JSON object only.'


class Unusable(ValueError):
    """An answer, or one change in it, that cannot be used; the reason is sent back to the model once."""


def connection_config(database) -> dict:
    with database.connect() as connection:
        config = config_for(connection, JOB)
    if config is None:
        raise DomainError('Add a text model in Settings > Models to use the Sidebar Assistant.', 409, 'no_connection')
    return config


def cut(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + '…'


def text_value(value, limit: int) -> str:
    return str(value).strip()[:limit] if isinstance(value, str | int | float) and not isinstance(value, bool) else ''


# --- What it is shown ------------------------------------------------------------------------------------------------

class Context:
    """The story as the sidebar sees it, each line, fact, person, arc and beat under a short reference."""

    def __init__(self, database, focus: str | None = None):
        self.lines, self.facts, self.people, self.arcs, self.beats = {}, {}, {}, {}, {}
        self.focus = None
        with database.connect() as connection:
            self.gm = record.gm_view(connection)
            self.note = authors_note.read(connection, CHAT)
            view = story.scene(connection, story_clock.now(connection, database.clock))
            self.scene = view
            rows = [row for row in story.messages(connection, RECENT_LINES)
                    if row['status'] == 'complete' and row['role'] in ('user', 'narrator')]
            if focus and all(row['id'] != focus for row in rows):
                rows = [found for found in [self.focused(connection, focus)] if found] + rows
            for index, row in enumerate(rows, 1):
                self.lines[f'm{index}'] = row
                if row['id'] == focus:
                    self.focus = f'm{index}'
            for index, row in enumerate(record.entries(connection, known_only=not self.gm)[:JOURNAL_LIMIT], 1):
                self.facts[f'k{index}'] = row
            self.lore = self.lore_rows(connection, view['city']['id'])
            for index, row in enumerate(feelings.met(connection), 1):
                self.people[f'p{index}'] = row
            if self.gm:
                self.behind(connection, view['city']['id'])

    @staticmethod
    def focused(connection, message_id: str) -> dict | None:
        """A line the user pointed the sidebar at that is older than the recent ones."""
        from adventure import timeline
        where, values = timeline.visible(connection)
        return optional(connection, f"SELECT id, seq, role, text, status FROM story_messages WHERE id=? AND {where} "
                                    "AND status='complete' AND role IN ('user', 'narrator')", (message_id, *values))

    def lore_rows(self, connection, city_id: str) -> list[dict]:
        """Lore switched on for this town: public only, or every entry while the GM view is on."""
        rows = many(connection, 'SELECT e.* FROM lore_entries e JOIN lore_books b ON b.id=e.book_id WHERE e.enabled=1 '
                                'AND b.enabled=1 AND (b.city_id IS NULL OR b.city_id=?) ORDER BY b.created_at, '
                                'e.position', (city_id,))
        return [row for row in rows if lore.readable(row, None if self.gm else frozenset())][:LORE_LIMIT]

    def behind(self, connection, city_id: str):
        world = tiers.world_of(city_id)
        plans = {plan['arc_id']: plan for plan in plotting.view(connection)['plans']}
        number = 0
        for index, arc in enumerate(gm.arcs(connection, world), 1):
            self.arcs[f'a{index}'] = arc
            for beat in plans.get(arc['id'], {}).get('beats', []):
                number += 1
                self.beats[f'b{number}'] = beat | {'arc_id': arc['id'], 'arc': arc['title']}

    # The sections of the prompt ----------------------------------------------------------------------------------

    def scene_text(self) -> str:
        view = self.scene
        place, city = view['place'], view['city']
        lines = [f"{place['name']}, a {place['kind']} in {place['neighborhood']}, {city['name']}.",
                 f"Local time: {view['local_time'].replace('T', ' ')}."]
        if view['weather']:
            lines.append(f"Weather: {view['weather']}")
        return '\n'.join(lines)

    def lines_text(self) -> str:
        if not self.lines:
            return 'The story has not started yet.'
        speaker = {'user': 'The user', 'narrator': 'The narrator'}
        return '\n'.join(f"[{ref}] {speaker[row['role']]}: {cut(row['text'], LINE_CHARS)}"
                         for ref, row in self.lines.items())

    def people_text(self) -> str:
        if not self.people:
            return 'Nobody yet.'
        return '\n'.join(f"[{ref}] {row['name']}" for ref, row in self.people.items())

    def journal_text(self) -> str:
        if not self.facts:
            return 'Nothing yet.'
        truth = {'world': ' (hidden from the character)', 'belief': ' (what the character believes)', 'both': ''}
        return '\n'.join(f"[{ref}] {row['kind']} · {row['subject']}: {row['text']}{truth.get(row['truth'], '')}"
                         for ref, row in self.facts.items())

    def lore_text(self) -> str:
        if not self.lore:
            return 'None.'
        lines = []
        for row in self.lore:
            when = 'always on' if row['always'] else f"keywords: {', '.join(decode(row['keywords']))}"
            hidden = ', GM only' if row['visibility'] != 'public' else ''
            lines.append(f"- {row['title'] or 'Untitled'} ({when}{hidden}): {cut(row['text'], LORE_CHARS)}")
        return '\n'.join(lines)

    def note_text(self) -> str:
        if not self.note['text']:
            return 'None yet.'
        state = 'on' if self.note['enabled'] else 'written but switched off'
        return f"({state}) {self.note['text']}"

    def feelings_text(self) -> str:
        if not self.people:
            return 'Nobody yet.'
        return '\n'.join(f"[{ref}] {row['name']}: " + ', '.join(f'{axis} {value}' for axis, value in feelings.of(row).items())
                         for ref, row in self.people.items())

    def arcs_text(self) -> str:
        if not self.arcs:
            return 'No arcs in this story.'
        lines = []
        for ref, arc in self.arcs.items():
            lines.append(f"[{ref}] {arc['title']}, stage {arc['stage'] + 1}: {arc['truth'] or 'no truth written'}")
            for beat_ref, beat in self.beats.items():
                if beat['arc_id'] == arc['id']:
                    state = ' (cut)' if beat['cut'] else ' (used)' if beat['used'] else ''
                    lines.append(f"  [{beat_ref}] {beat['text']}{state}")
        return '\n'.join(lines)

    def view_text(self, view: str) -> str:
        where = VIEW_NAMES.get(view.split('/')[0], 'the app')
        focus = f' They pointed you at [{self.focus}].' if self.focus else ''
        return f'The user is looking at {where}.{focus}'

    def system(self, view: str) -> str:
        return SYSTEM.format(
            gm_tools=GM_TOOLS if self.gm else '', view=self.view_text(view), scene=self.scene_text(),
            lines=self.lines_text(), people=self.people_text(), journal=self.journal_text(),
            journal_note=', and with the GM view on, what is hidden from them' if self.gm else '', lore=self.lore_text(),
            note=self.note_text(),
            gm_context=GM_CONTEXT.format(feelings=self.feelings_text(), arcs=self.arcs_text()) if self.gm else '',
            secret_field=', "secret": false' if self.gm else '', gm_kinds=GM_KINDS if self.gm else '')


# --- What it may propose ---------------------------------------------------------------------------------------------

class Proposals:
    """The reply and its changes, each checked against the context; one unusable change is sent back once, then
    dropped."""

    def __init__(self, context: Context):
        self.context = context
        self.handlers = {'authors_note': self.authors_note, 'narration': self.narration,
                         'journal_add': self.journal_add, 'journal_fix': self.journal_fix, 'lore_add': self.lore_add}
        self.gm_handlers = {'feelings': self.feelings, 'beat_cut': self.beat_cut, 'beat_add': self.beat_add}

    def __call__(self, raw, final: bool) -> dict:
        if not isinstance(raw, dict):
            raise Unusable('it was not one JSON object.')
        reply = text_value(raw.get('reply'), REPLY_CHARS)
        changes = []
        for item in raw.get('changes') if isinstance(raw.get('changes'), list) else []:
            try:
                changes.append(self.change(item))
            except Unusable:
                if not final:
                    raise
        if not reply:
            if not final:
                raise Unusable('"reply" was empty.')
            reply = 'Here is what I would change.' if changes else 'I have nothing to change.'
        return {'reply': reply, 'changes': changes, 'gm': self.context.gm}

    def change(self, item) -> dict:
        if not isinstance(item, dict):
            raise Unusable('each change must be an object.')
        kind = item.get('kind')
        if kind in self.gm_handlers and not self.context.gm:
            raise Unusable(f'{kind} needs the GM view, which is off.')
        handler = self.handlers.get(kind) or (self.gm_handlers.get(kind) if self.context.gm else None)
        if handler is None:
            allowed = [*self.handlers, *(self.gm_handlers if self.context.gm else [])]
            raise Unusable(f'a change had kind {kind!r}; use one of {", ".join(allowed)}.')
        return handler(item)

    def referred(self, table: dict, item: dict, what: str) -> dict:
        found = table.get(item.get('ref'))
        if found is None:
            raise Unusable(f'{item.get("ref")!r} is not one of the {what} you were shown.')
        return found

    def authors_note(self, item) -> dict:
        text = text_value(item.get('text'), authors_note.LIMIT)
        if not text:
            raise Unusable('an author\'s note change had no "text".')
        note = self.context.note
        return {'kind': 'authors_note', 'before': note['text'], 'enabled': note['enabled'], 'text': text}

    def narration(self, item) -> dict:
        row = self.referred(self.context.lines, item, 'lines')
        if row['role'] != 'narrator':
            raise Unusable(f"[{item.get('ref')}] is the user's own line; only the narrator's passages can be reworded.")
        text = text_value(item.get('text'), NARRATION_CHARS)
        if not text:
            raise Unusable('a narration change had no "text".')
        return {'kind': 'narration', 'message_id': row['id'], 'before': row['text'], 'text': text}

    def journal_add(self, item) -> dict:
        subject, text = text_value(item.get('subject'), 120), text_value(item.get('text'), 500)
        if not subject or not text:
            raise Unusable('a new journal fact needs "subject" and "text".')
        return {'kind': 'journal_add', 'subject': subject, 'text': text}

    def journal_fix(self, item) -> dict:
        row = self.referred(self.context.facts, item, 'journal facts')
        text = text_value(item.get('text'), 500)
        label = f"{row['kind']} · {row['subject']}:"
        if text.lower().startswith(label.lower()):
            text = text[len(label):].strip()
        if not text:
            raise Unusable('a journal correction had no "text".')
        return {'kind': 'journal_fix', 'entry_id': row['id'], 'subject': row['subject'], 'before': row['text'],
                'text': text}

    def lore_add(self, item) -> dict:
        text = text_value(item.get('text'), 4000)
        keywords = [word for word in (text_value(word, 80) for word in item.get('keywords') or []
                                      if isinstance(item.get('keywords'), list)) if word][:lore.MAX_KEYWORDS]
        always = item.get('always') is True
        if not text or not (always or keywords):
            raise Unusable('a lore entry needs "text", and "keywords" unless it is always on.')
        secret = self.context.gm and item.get('secret') is True
        return {'kind': 'lore_add', 'title': text_value(item.get('title'), 200), 'text': text, 'keywords': keywords,
                'always': always, 'visibility': 'gm' if secret else 'public'}

    def feelings(self, item) -> dict:
        row = self.referred(self.context.people, item, 'people')
        before, values = feelings.of(row), {}
        for axis in feelings.AXES:
            value = item.get(axis)
            if isinstance(value, int) and not isinstance(value, bool):
                values[axis] = max(feelings.LOW[axis], min(feelings.HIGH, value))
        values = {axis: value for axis, value in values.items() if value != before[axis]}
        if not values:
            raise Unusable(f"a feelings change for [{item.get('ref')}] changed nothing.")
        return {'kind': 'feelings', 'key': row['key'], 'name': row['name'], 'before': before, 'values': values}

    def beat_cut(self, item) -> dict:
        beat = self.referred(self.context.beats, item, 'beats')
        cut_it = item.get('cut') is not False
        if bool(beat['cut']) == cut_it:
            raise Unusable(f"[{item.get('ref')}] is already {'cut' if cut_it else 'in the plan'}.")
        return {'kind': 'beat_cut', 'beat_id': beat['id'], 'arc': beat['arc'], 'text': beat['text'], 'cut': cut_it}

    def beat_add(self, item) -> dict:
        arc = self.referred(self.context.arcs, item, 'arcs')
        text = ' '.join(text_value(item.get('text'), 300).split())
        if not text:
            raise Unusable('a new beat had no "text".')
        return {'kind': 'beat_add', 'arc_id': arc['id'], 'arc': arc['title'], 'text': text}


def read(answer: str):
    """The answer's JSON object, or Unusable."""
    found = record.read_json(answer)
    if found is None:
        raise Unusable('it was not one JSON object.')
    return found


async def chat(state, body) -> dict:
    """One sidebar message: a reply, and proposed changes the user reviews. Nothing is stored or applied."""
    config = connection_config(state.database)
    context = Context(state.database, body.focus_message_id)
    messages = [{'role': turn.role, 'content': turn.content} for turn in body.history]
    messages.append({'role': 'user', 'content': body.message})
    while messages and messages[0]['role'] != 'user':
        messages.pop(0)
    system, proposals = context.system(body.view), Proposals(context)
    answer = await story.complete(state, config, system, messages)
    try:
        return proposals(read(answer), final=False)
    except Unusable as reason:
        again = [*messages, {'role': 'assistant', 'content': answer},
                 {'role': 'user', 'content': RETRY.format(reason=reason)}]
        answer = await story.complete(state, config, system, again)
    try:
        return proposals(read(answer), final=True)
    except Unusable:
        # A model that will not answer in JSON still answers: its words, with nothing to apply.
        return {'reply': cut(answer.strip(), REPLY_CHARS) or 'I could not answer that. Try again.', 'changes': [],
                'gm': context.gm}

