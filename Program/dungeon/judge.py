"""The judge of Narrative Only (dungeon/rules/narrative.py; docs/requirements.md "Narrative Only").

Under Narrative Only each of a turn's actions gets a verdict instead of a roll: No, No, but, Yes, but or Yes, with a
one-line reason. The judge is a model (the Referee's own, else the narrator's), asked once per turn about all of the
turn's actions together. It reads who the character is (their own description, their wounds and lasting injuries),
the player's words, the scene with the people in it and how they feel toward the character, and the actions with the
difficulty the Referee and code gave each. It is not the narrator: it decides, and the narrator writes what it
decided. With no model, or an answer that cannot be read, the difficulty decides each one in code (narrative.result).
"""
from dungeon import combat, record, referee
from dungeon.rules import narrative
from dungeon.sheet import ruleset
from dungeon.text_models import config_for
from dungeon.world import intimacy

SYSTEM = """You judge a tabletop game run with no stats and no dice. For each numbered action the player's character \
attempts, decide what happens, as a fair and realistic game master would: a gut check of who this character is (their \
own description, body, wounds, skills and history), how well the player's words go about it (a careful, specific \
approach does better than a bare wish), who they are dealing with (that person's feelings toward the character, \
wants, fears, mood, and the moment), and what the world allows. Good outcomes are not owed: a long shot fails most of \
the time, and a sure thing usually works. When an action flirts with, seduces or courts someone, weigh who that \
person is drawn to (their private attractions, when given): someone whose orientation or tastes leave the character \
out is a long shot however well it is said, and someone the character's manner or mind draws in is an easier one. \
Answer each with one verdict:
- yes: it works.
- yes_but: it works, at a cost or with a complication.
- no_but: it fails, but something is gained or learned.
- no: it fails.
And one short reason in plain words, naming what decided it (for "no_but", also what is gained). Answer with JSON only: \
{"verdicts": [{"verdict": "...", "reason": "..."}, ...]}, one per action, in order."""
SHAPE = {'type': 'object', 'required': ['verdicts'], 'properties': {'verdicts': {'type': 'array', 'items': {
    'type': 'object', 'required': ['verdict', 'reason'], 'properties': {
        'verdict': {'type': 'string', 'enum': list(narrative.VERDICTS)}, 'reason': {'type': 'string'}}}}}}
DIFFICULTY = {'easy': 'easy', 'normal': 'ordinary', 'hard': 'hard', 'very_hard': 'very hard', 'extreme': 'extreme'}


def model(connection) -> dict | None:
    return referee.own_model(connection) or config_for(connection, 'story')


def attractions(connection, people: list[dict]) -> str:
    """Who the adults here are drawn to (dungeon/world/intimacy.py), while the adult side is on. Never shown and
    never narrated: it only moves a romantic or seductive action's verdict."""
    if not intimacy.turned_on(connection):
        return ''
    lines = []
    for person in people:
        sheet = person.get('sheet') or {}
        found = intimacy.for_sheet(sheet) if sheet.get('seed') and sheet.get('full') else None
        if said := intimacy.attraction_text(found):
            lines.append(f"- {sheet['full']}: {said}.")
    return ('## Who the people here are drawn to (private; for romance and seduction only)\n' + '\n'.join(lines)
            if lines else '')


def asking(connection, persona: str, scene: str, text: str, actions: list[dict],
           people: list[dict] | None = None) -> dict | None:
    """What the judge is asked this turn, and the model to ask; None outside Narrative Only, with nothing to judge,
    or with no model (the difficulty then decides). `people` are the scene's people, for who they are drawn to."""
    config = model(connection) if actions and ruleset(connection) == narrative.ID else None
    if config is None:
        return None
    body = combat.condition_text(connection)
    numbered = [f"{number}. {action['action']} (on its face: {DIFFICULTY.get(action['difficulty'], 'ordinary')})"
                for number, action in enumerate(actions, 1)]
    told = '\n\n'.join(part for part in (
        f"## The player's character\n{persona}" if persona else '', f'Their condition: {body}' if body else '',
        scene, attractions(connection, people or []), f'## What the player wrote\n{text}', '## The actions to judge\n' + '\n'.join(numbered)) if part)
    return {'config': config, 'text': told}


def verdicts(answer: str, count: int) -> list[dict] | None:
    data = record.read_json(answer)
    found = data.get('verdicts') if isinstance(data, dict) else None
    if not isinstance(found, list) or len(found) < count:
        return None
    kept = [item if isinstance(item, dict) and item.get('verdict') in narrative.VERDICTS else {} for item in found]
    return [{'verdict': item.get('verdict'), 'reason': str(item.get('reason') or '')[:240]} for item in kept[:count]]


async def judged(state, actions: list[dict], ask: dict) -> list[dict]:
    """The actions, each with the judge's verdict (`judged`); left as they were when the judge cannot answer."""
    try:
        answer = await record.schema_first(state, ask['config'], SYSTEM, ask['text'], SHAPE,
                                           lambda answer: verdicts(answer, len(actions)) is not None)
    except Exception:  # noqa: BLE001 - with no judge the difficulty decides; the turn goes on.
        return actions
    found = verdicts(answer, len(actions))
    return [action | {'judged': verdict} for action, verdict in zip(actions, found)] if found else actions
