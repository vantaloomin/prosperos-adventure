"""Resolve for a party: code decides every outcome for every character, as Dungeon does for one (docs/spec.md "The
turn loop" step 7, "Rolls, overrides and the turn report").

Each character's declared intent is split into acts (one a sentence, as the Referee splits a line). For each act:

- **Code classifies the risky kinds it can see** (`KINDS`): an attack, a theft, a deception, persuasion or a threat.
  Those always roll, and when aimed at someone present that someone resists with their own roll: when they do
  better, the act lands a step worse (as a shopkeeper holds firm on a haggle, adventure/inventory.py opposed).
- **The Referee rules on the rest** (adventure/referee.py decide) seeing the bare intent only: never the
  character's lines, motive, lies or whispers, so a good pitch or a hidden plan never moves the odds.
- **Code rolls.** Everyone but the player's character rolls on the shared ladder with their stat
  (adventure/rules/marvel.py roll; the stat from character_stats, else the default); the player's own line is
  rolled by today's turn on their sheet in the campaign's ruleset (adventure/story.py resolved), so it is not
  rolled again here. Under Narrative Only no judge model decides a character's act: code gives the verdict from the
  difficulty (adventure/rules/narrative.py result).
- **Declared lies are rolled where they are heard** (adventure/rounds/lies_heard.py, before React). Resolve does
  not roll them again; it carries their outcomes into the brief.

The output is the immutable TurnResult in `draft.result`: every roll labelled with who acts (`actor`, a seat key),
at whom (`target`, a seat key or ''), the kind, what is at stake, the stat and the band; each outcome in plain
words; and the brief the Writer renders (when and where, the user's beats, each uncertain outcome with its roll, the
math, the stop point). The rolls are written to `round_rolls` at Commit for the dice log.
"""
import random
import re
from dataclasses import dataclass

from adventure import pace, referee, sheet
from adventure.database import identifier, many
from adventure.rounds import engine
from adventure.rounds.contract import Brief, Declaration, Mind, Mode, Seat, State, TurnResult
from adventure.rules import ladder, marvel, narrative

# The risky kinds code knows on sight, in the order they are tried: the stat the act tests and the stat the one it
# is aimed at resists with.
KINDS = (
    ('attack', 'Vitality', 'Vitality', re.compile(
        r'\b(attack\w*|stab\w*|slash\w*|punch\w*|kick\w*|shoot\w*|kill\w*|hit\w*|strike\w*|struck|swing\w* at|'
        r'lunge\w* at|tackle\w*|shove\w*|throttl\w*|strangl\w*|headbutt\w*|club\w*|bash\w*|cut\w* (at|down))\b',
        re.I)),
    ('steal', 'Mind', 'Mind', re.compile(
        r'\b(steal\w*|stole|pickpocket\w*|pilfer\w*|filch\w*|swipe\w*|snatch\w*|pinch\w*|rob\w*|lift\w* (his|her|'
        r'their|the)|pocket\w* (his|her|their|the))\b', re.I)),
    ('deceive', 'Allure', 'Mind', re.compile(
        r'\b(lie\w* (to|about)|lying (to|about)|lied (to|about)|bluff\w*|deceiv\w*|trick\w*|mislead\w*|misled|'
        r'fool\w*|con\w* (him|her|them)|pass\w* (myself|himself|herself|themselves) off)\b', re.I)),
    ('persuade', 'Allure', 'Resolve', re.compile(
        r'\b(persuad\w*|convinc\w*|talk\w* \w+ (into|out of)|coax\w*|cajol\w*|sway\w*|win\w* (him|her|them) over|'
        r'bribe\w*|plead\w* with|seduc\w*|charm\w*)\b', re.I)),
    ('threaten', 'Resolve', 'Resolve', re.compile(
        r'\b(threat\w*|intimidat\w*|menac\w*|coerc\w*|blackmail\w*|bull(y|ies|ied)|stare\w* (him|her|them) down)\b',
        re.I)),
)
STAKES = {'attack': 'hurting {target}', 'steal': 'taking it without {target} noticing',
          'deceive': '{target} believing it', 'persuade': '{target} going along with it',
          'threaten': '{target} backing down'}
# The kind of the rolls of the player's own line, rolled by today's turn and kept in story_rolls.
LINE = 'line'
UNAIMED = {'attack': 'landing the blow', 'steal': 'taking it unseen', 'deceive': 'being believed',
           'persuade': 'winning them over', 'threaten': 'being taken seriously'}


@dataclass
class Act:
    """One thing one character tries this turn: `kind` is one of KINDS, or 'referee' for what the Referee ruled
    uncertain; `target` the seat key it is aimed at, or ''."""
    actor: str
    action: str
    kind: str
    stat: str
    difficulty: str = 'normal'
    target: str = ''
    resist: str = ''


# Splitting intents into acts ----------------------------------------------------------------------------------------

def aimed(text: str, seats: list[Seat], actor: str) -> str:
    """The seat an act names, by full or first name; '' when it names nobody at the table (or names its actor)."""
    lowered = text.lower()
    for seat in seats:
        names = {seat.name.lower(), seat.name.split()[0].lower()} if seat.name.strip() else set()
        if seat.key != actor and any(re.search(rf'\b{re.escape(name)}\b', lowered) for name in names):
            return seat.key
    return ''


def classified(actor: str, part: str, seats: list[Seat]) -> Act | None:
    """The act as code reads it, when it is one of the risky kinds."""
    for kind, stat, resist, pattern in KINDS:
        if pattern.search(part):
            target = aimed(part, seats, actor)
            return Act(actor, part, kind, stat, target=target, resist=resist if target else '')
    return None


def split(declaration: Declaration, seats: list[Seat]) -> tuple[list[Act], list[str]]:
    """The intent's risky acts code can see, and the parts left for the Referee. A lie the character declared as one
    is rolled where it is heard, so its part of the intent is not rolled again."""
    acts, rest = [], []
    for part in referee.sentences(declaration.intent)[:referee.MOST_ACTIONS]:
        act = classified(declaration.seat, part, seats)
        if act and act.kind == 'deceive' and declaration.deceptions:
            continue
        if act:
            acts.append(act)
        else:
            rest.append(part)
    return acts, rest


async def ruled(app, actor: str, rest: list[str], seats: list[Seat], models: tuple) -> list[Act]:
    """What the Referee rules uncertain among the parts code could not classify, from the bare intent alone."""
    text = '. '.join(rest)
    if not text.strip():
        return []
    splitter, decisions = models
    obvious = pace.obvious(text)
    actions = await referee.decide(app, text, None if obvious else splitter, None if obvious else decisions)
    return [Act(actor, action['action'], 'referee', action['stat'], action.get('difficulty', 'normal'),
                target=aimed(action['action'], seats, actor)) for action in actions if action.get('roll')]


# Ambiguity ----------------------------------------------------------------------------------------------------------

# Words that point at someone without naming them.
POINTING = re.compile(r'\b(him|her|them|that one|this one|one of them|someone|somebody|the other)\b', re.I)
ASKER = 'GM'


def question(said: str, seats: list[Seat], present: list[str], human: str) -> str | None:
    """One focused question, when the player's move is risky and points at someone without saying who, with more than
    one character there it could mean (docs/spec.md "Ambiguity gets one question"); None when it is clear enough."""
    others = [seat for seat in seats if seat.key in present and seat.key != human]
    if len(others) < 2:
        return None
    for part in referee.sentences(said):
        act = classified(human, part, seats)
        if act and not act.target and POINTING.search(part):
            names = [seat.name for seat in others]
            return f"Who do you mean: {', '.join(names[:-1])} or {names[-1]}?"
    return None


async def ambiguity(turn):
    """Resolving, before anything is rolled: ask the player once when their move is ambiguous on who it is aimed at,
    on the reply card, and keep what they meant (`draft.extra['resolve']['meant']`) for the line's telling."""
    staged = turn.draft.extra.setdefault('resolve', {})
    human = turn.snapshot.human()
    if human is None or turn.snapshot.mode != Mode.PLAY or 'meant' in staged:
        return
    if staged.get('asked'):
        reply = turn.draft.replies.get(human.key) or {}
        staged['meant'] = reply.get('text', '') if reply.get('kind') == 'reply' else ''
        return
    said = turn.snapshot.settings.get('said', '')
    asked = question(said, turn.snapshot.seats, turn.snapshot.present, human.key)
    if asked:
        staged['asked'] = asked
        turn.draft.wait_for(human.key, ASKER, asked, [said])


def meant(said: str, turn) -> str:
    """The player's line as Resolve reads it, with their answer to the one question when there was one."""
    answer = (turn.draft.extra.get('resolve') or {}).get('meant', '').strip()
    return f'{said} (meaning {answer})' if answer else said


# Rolling --------------------------------------------------------------------------------------------------------------

def stat_value(connection, key: str, stat: str, seats: list[Seat]) -> int:
    """A character's stat: the player's character's from their sheet, anyone else's from character_stats, else the
    default."""
    seat = next((seat for seat in seats if seat.key == key), None)
    actor = sheet.PERSONA if seat is not None and seat.mind == Mind.HUMAN else key
    return sheet.stats(connection, actor).get(stat, marvel.DEFAULT_STAT)


def worse(band: str) -> str:
    return ladder.BANDS[max(0, ladder.BANDS.index(band) - 1)]


def rolled(connection, act: Act, seats: list[Seat], ruleset: str, rng) -> dict:
    """One act rolled by code, opposed by its target when it has one. Under Narrative Only the difficulty gives the
    verdict, with no die and no judge."""
    names = {seat.key: seat.name for seat in seats}
    stake = (STAKES[act.kind].format(target=names.get(act.target, act.target)) if act.target and act.kind in STAKES
             else UNAIMED.get(act.kind, act.action))
    if ruleset == narrative.ID:
        result = narrative.result(None, '', act.difficulty)
        opposed = None
    else:
        result = marvel.roll(stat_value(connection, act.actor, act.stat, seats), act.difficulty, rng) | {
            'ruleset': marvel.ID}
        opposed = None
        if act.target and act.resist:
            against = marvel.roll(stat_value(connection, act.target, act.resist, seats), 'normal', rng)
            opposed = {'stat': act.resist, 'band': against['band'], 'natural': against['natural'],
                       'bonus': against['bonus'], 'total': against['total']}
            if ladder.BANDS.index(against['band']) > ladder.BANDS.index(result['band']):
                result = result | {'band': worse(result['band'])}
    return {'actor': act.actor, 'target': act.target, 'kind': act.kind, 'stake': stake, 'action': act.action,
            'stat': act.stat, 'difficulty': act.difficulty, 'die': result.get('die'),
            'natural': result.get('natural', 0), 'bonus': result.get('bonus', 0), 'shift': result.get('shift', 0),
            'total': result.get('total', 0), 'band': result['band'], 'ruleset': result['ruleset'],
            'verdict': result.get('verdict'), 'opposed': opposed}


# The result and the brief -------------------------------------------------------------------------------------------

def outcome(roll: dict, names: dict[str, str]) -> dict:
    return {'actor': names.get(roll['actor'], roll['actor']), 'action': roll['action'], 'kind': roll['kind'],
            'target': names.get(roll['target'], roll['target']), 'stake': roll['stake'], 'band': roll['band'],
            'landed': ladder.succeeded(roll['band'])}


def outcome_line(roll: dict, names: dict[str, str]) -> str:
    """'Hesk: "I cut Mara down" (Vitality, against Mara's Vitality; at stake: hurting Mara): Success at a cost.'"""
    against = f", against {names.get(roll['target'], roll['target'])}'s {roll['opposed']['stat']}" \
        if roll.get('opposed') else ''
    return (f"{names.get(roll['actor'], roll['actor'])}: \"{roll['action']}\" ({roll['stat']}{against}; at stake: "
            f"{roll['stake']}): {ladder.LABELS[roll['band']]}.")


def math_line(roll: dict, names: dict[str, str]) -> str:
    """The arithmetic of one roll, for the report and a System pane; never for the prose."""
    who = names.get(roll['actor'], roll['actor'])
    if roll['ruleset'] == narrative.ID:
        return f"{who}: {roll['difficulty'].replace('_', ' ')} on its face, so {narrative.VERDICTS[roll['verdict']]}."
    die = f" + d{roll['die']} {roll['bonus']}" if roll.get('die') else ''
    shift = f" - {roll['shift']}" if roll['shift'] > 0 else f" + {-roll['shift']}" if roll['shift'] < 0 else ''
    against = f"; resisted with {roll['opposed']['total']}" if roll.get('opposed') else ''
    return f"{who}: d100 {roll['natural']}{die}{shift} = {roll['total']}{against}: {ladder.LABELS[roll['band']]}."


def heard_lies(draft, names: dict[str, str]) -> list[str]:
    """The declared lies as they were rolled when heard (adventure/rounds/lies_heard.py), for the brief."""
    lines = []
    for lie in (draft.extra.get('agents') or {}).get('lies', []):
        caught = 'sees through it' if lie.get('caught') else 'believes it'
        lines.append(f"{names.get(lie.get('liar'), lie.get('liar'))} lies to "
                     f"{names.get(lie.get('listener'), lie.get('listener'))} ({lie.get('claim', '')}): the listener "
                     f'{caught}.')
    return lines


def stop_point(snapshot) -> str:
    """Where the Writer stops (docs/spec.md "The turn brief and the stop point")."""
    human = snapshot.human()
    if snapshot.mode == Mode.PLAY and human is not None:
        return f"Before {human.name}'s next real decision."
    return 'At the next natural break or big moment.'


def scene_of(turn) -> tuple[str, str]:
    """When and where the turn happens: as Gather froze it, else the story's scene now."""
    settings = turn.snapshot.settings
    if settings.get('when') or settings.get('where'):
        return settings.get('when', ''), settings.get('where', '')
    from adventure import story, story_clock
    with turn.database.connect() as connection:
        view = story.scene(connection, story_clock.now(connection, turn.database.clock))
    return view['local_time'].replace('T', ' '), f"{view['place']['name']}, {view['city']['name']}"


def brief(turn, rolls: list[dict], names: dict[str, str]) -> Brief:
    settings = turn.snapshot.settings
    when, where = scene_of(turn)
    return Brief(when=when, where=where, beats=list(settings.get('beats', [])),
                 outcomes=[outcome_line(roll, names) for roll in rolls] + heard_lies(turn.draft, names),
                 math=[math_line(roll, names) for roll in rolls], stop_point=stop_point(turn.snapshot))


def ally_moves(turn) -> dict[str, str]:
    """The agent allies' declared moves for a fight round (adventure/allies.py): an agent's own intent. A character
    on its Program mind this turn (or fallen back to it) keeps code's tactic."""
    return {key: declaration.intent for key, declaration in turn.draft.declarations.items()
            if (seat := turn.snapshot.seat(key)) is not None and seat.mind == Mind.AGENT and not declaration.fallback
            and declaration.intent.strip()}


def fighting(connection, acts: list[Act], turn) -> list[Act]:
    """In a fight, an agent ally's blow is rolled by the fight round with their declared move, not again here."""
    from adventure import combat, party
    if combat.fight(connection) is None:
        return acts
    moving, allies = ally_moves(turn), party.keys(connection)
    return [act for act in acts if not (act.kind == 'attack' and act.actor in moving and act.actor in allies)]


def actors(turn) -> list[Declaration]:
    """The declarations Resolve rolls, in seat order: everyone's but the human's, whose line today's turn rolls."""
    order = {seat.key: seat.order for seat in turn.snapshot.seats}
    human = turn.snapshot.human()
    return sorted((declaration for key, declaration in turn.draft.declarations.items()
                   if human is None or key != human.key or turn.snapshot.mode != Mode.PLAY),
                  key=lambda declaration: order.get(declaration.seat, len(order)))


async def acts_of(turn, declarations: list[Declaration]) -> list[Act]:
    with turn.database.connect() as connection:
        models = (referee.own_model(connection), referee.decision_model(connection))
    acts = []
    for declaration in declarations:
        found, rest = split(declaration, turn.snapshot.seats)
        acts += found + await ruled(turn.app, declaration.seat, rest, turn.snapshot.seats, models)
    return acts


async def resolve(turn):
    """Resolving's step: every character's risky acts rolled by code, into the turn's TurnResult. The rolls of the
    player's own line (today's turn, `draft.extra['resolve']['line_rolls']`) come first, as they stand."""
    declarations = actors(turn)
    staged = turn.draft.extra.setdefault('resolve', {})
    acts = await acts_of(turn, declarations)
    rng = getattr(turn.app, 'dice', None) or random.SystemRandom()
    with turn.database.connect() as connection:
        ruleset = sheet.ruleset(connection)
        rolls = [*staged.get('line_rolls', []), *(rolled(connection, act, turn.snapshot.seats, ruleset, rng)
                                                    for act in fighting(connection, acts, turn))]
    names = {seat.key: seat.name for seat in turn.snapshot.seats}
    turn.draft.result = TurnResult(declarations=list(turn.draft.declarations.values()), rolls=rolls,
                                   outcomes=[outcome(roll, names) for roll in rolls], brief=brief(turn, rolls, names))


# Commit ---------------------------------------------------------------------------------------------------------------

def kept_rolls(connection, turn):
    """The turn's rolls by the other characters, for the dice log (the player's own line keeps its rolls in
    story_rolls, adventure/turn.py)."""
    result = turn.draft.result
    if result is None:
        return
    now, message_id = turn.database.now(), turn.snapshot.settings.get('message_id')
    for position, roll in enumerate(roll for roll in result.rolls if roll.get('kind') != LINE):
        connection.execute(
            'INSERT INTO round_rolls (id, turn_id, message_id, position, actor, target, kind, stake, action, stat, '
            'difficulty, die, natural, bonus, shift, total, band, ruleset, against, created_at) VALUES (?, ?, ?, ?, '
            '?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (identifier(), turn.id, message_id, position, roll['actor'], roll.get('target', ''), roll.get('kind') or 'referee',
             roll.get('stake', ''), roll.get('action', ''), roll.get('stat', ''), roll.get('difficulty', 'normal'),
             roll.get('die'), roll.get('natural', 0), roll.get('bonus', 0), roll.get('shift', 0), roll.get('total', 0),
             roll['band'], roll.get('ruleset', marvel.ID),
             roll['opposed']['band'] if roll.get('opposed') else None, now))


def saved(connection, message_id: str) -> list[dict]:
    """The other characters' rolls on a story line, for the dice log."""
    return many(connection, "SELECT r.* FROM round_rolls r JOIN round_turns t ON t.id = r.turn_id "
                            "WHERE r.message_id=? AND t.state='committed' ORDER BY r.created_at, r.position",
                (message_id,))


def shown(row: dict, names: dict[str, str]) -> dict:
    """Another character's roll as the dice log shows it: who rolled, at whom, and the dice."""
    return {key: row[key] for key in ('action', 'stat', 'difficulty', 'die', 'natural', 'bonus', 'shift', 'total',
                                      'band', 'ruleset', 'kind', 'stake')} | {
        'actor': names.get(row['actor'], row['actor']), 'against': names.get(row['target'], row['target']),
        'label': ladder.LABELS[row['band']], 'target': None, 'skill': None}


engine.register(State.RESOLVING, 'ambiguity', ambiguity)
engine.register(State.RESOLVING, 'resolve', resolve)
engine.on_commit('rolls', kept_rolls)
