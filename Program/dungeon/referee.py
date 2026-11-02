"""The Referee (docs/requirements.md "Turn loop" and "Referee model"): splits the player's intent into actions and
decides, for each, whether it needs a roll, which Prospero stat and how hard it is. Code then rolls.

A text model does it when one is chosen for the Referee job in Settings > Models; it answers in JSON and anything
it gets wrong is dropped. Without one, or when its answer cannot be read, keyword rules decide. The narrator's own
model is never borrowed for this, so a turn costs one narrator call unless the player asks for more.

A decision model, when one is chosen for Referee decisions, then decides each action's roll, stat and difficulty from
the odds it gives each answer (dungeon/providers/decisions.py), over the Referee's split or, without a Referee profile,
each sentence of the turn. It writes no text, so it costs one short read per action. That one may be the narrator's
own local model, since asking it for one token's odds is not a narrator call.
"""
import asyncio
import json
import re

from dungeon.providers.scheduling import CONVERSATION
from dungeon.rules import marvel
from dungeon.text_models import config_for, key_for, routes

JOB = 'referee'
DECISIONS = 'decisions'
MOST_ACTIONS = 4
# An action rolls when the decision model thinks it is at least this likely to need one.
ROLL_AT = 0.5

# Words that make an action uncertain, and the stat they test. The first stat with a match wins, so the more
# specific lists come first.
KEYWORDS = (
    ('Essence', ('cast', 'spell', 'magic', 'pray', 'ritual', 'channel', 'enchant', 'curse', 'ward', 'hex', 'summon',
                 'bless', 'heal')),
    ('Allure', ('persuade', 'convince', 'charm', 'flirt', 'seduce', 'lie', 'bluff', 'haggle', 'bargain', 'deceive',
                'perform', 'sing', 'negotiate', 'beg', 'taunt', 'flatter', 'talk them', 'talk him', 'talk her',
                'talk the', 'talk my way', 'talk our way', 'sweet-talk')),
    ('Resolve', ('resist', 'withstand', 'intimidate', 'stare down', 'refuse to', 'hold my ground', 'keep calm',
                 'steady', 'endure the', 'threaten', 'command')),
    ('Vitality', ('attack', 'hit', 'punch', 'strike', 'fight', 'swing', 'stab', 'slash', 'shoot', 'lift', 'shove',
                  'push', 'run', 'climb', 'jump', 'leap', 'wrestle', 'grab', 'tackle', 'kick', 'break', 'force',
                  'swim', 'chase', 'flee', 'dodge', 'block', 'parry', 'carry', 'hack', 'lunge', 'thrust', 'smash',
                  'bash', 'headbutt', 'throttle', 'strangle')),
    ('Mind', ('search', 'examine', 'study', 'recall', 'remember', 'notice', 'spot', 'investigate', 'deduce',
              'figure out', 'pick the lock', 'pick a lock', 'track', 'listen', 'read the', 'decipher', 'steal',
              'pickpocket', 'forge', 'repair', 'treat the', 'patch', 'for anyone', 'for anybody', 'for someone',
              'watching me', 'following me', 'tailing me', 'being watched', 'being followed', 'keep an eye',
              'look out for', 'on the lookout', 'scan the')),
    ('Luck', ('sneak', 'hide', 'gamble', 'bet', 'guess', 'hope', 'slip past', 'luck')),
)

STATS = '; '.join(f'{stat} ({meaning})' for stat, meaning in marvel.MEANINGS.items())

SYSTEM = f"""You are the Referee of a tabletop roleplaying game. You never write story. Read the player's turn and \
split it into the separate things their character tries to do, at most {MOST_ACTIONS}. For each one decide whether \
the outcome is uncertain enough to need a roll (talking, looking around, walking somewhere or ordinary actions do \
not), which stat it tests and how hard it is.

Stats: {STATS}.
Difficulty: easy, normal, hard, very_hard or extreme.

Answer with JSON only, in this shape:
{{"actions": [{{"action": "what they try, in a few words", "roll": true, "stat": "Vitality", "difficulty": "hard"}}]}}"""


# The three questions a decision model answers for each action, in Jev's shapes.
QUESTIONS = {
    'roll': {'type': 'noul', 'instructions': 'Is the outcome of this action uncertain enough to need a dice roll? '
             'Talking, looking around, walking somewhere and ordinary everyday actions do not need one.'},
    'stat': {'type': 'choice', 'instructions': 'Which stat does this action test?', 'criteria': dict(marvel.MEANINGS)},
    'difficulty': {'type': 'score', 'instructions': 'How hard is this action for a capable adult?',
                   'criteria': ['Easy: it would rarely go wrong', 'Normal: a fair chance either way for most people',
                                'Hard: it takes real skill or luck', 'Very hard: most people would fail',
                                'Extreme: only the best, with luck, could do it']},
}
LEVELS = tuple(marvel.DIFFICULTIES)  # easy to extreme, as the difficulty question lists them.


def sentences(text: str) -> list[str]:
    parts = re.split(r'(?<=[.!?])\s+|\s+(?:and then|then)\s+', text.strip(), flags=re.I)
    parts = [re.sub(r'^(?:and then|then|and)\s+', '', part.strip(' .!?'), flags=re.I) for part in parts]
    return [part for part in parts if part]


def stat_for(text: str) -> str | None:
    lowered = text.lower()
    for stat, words in KEYWORDS:
        if any(re.search(rf'\b{re.escape(word)}', lowered) for word in words):
            return stat
    return None


# Mid-fight, a line that keeps at the foe is an attack though it names no blow ("I keep at him", "again").
PRESSING = re.compile(r'\b(keeps? at|again|finish (?:him|her|it|them|off)|go(?:es)? at|lays? into|have at|'
                      r'press(?:es)? (?:the attack|on|him|her|them)|another (?:blow|swing|punch|cut))', re.I)


def fight_note(fight: str) -> str:
    """What the Referee is told when a fight is on, before the player's turn."""
    return (f"A fight is on: the player's character is fighting {fight}. An action aimed at a foe, or one that keeps "
            "the fight going (\"I keep at him\", \"again\"), is an attack: it rolls Vitality.\n\nThe player's turn: ")


def by_keywords(text: str, fight: str | None = None) -> list[dict]:
    """The rules with no model: each sentence that names something uncertain is an action at normal difficulty."""
    actions = []
    for part in sentences(text):
        stat = 'Vitality' if fight and PRESSING.search(part) else stat_for(part)
        if stat:
            actions.append({'action': part, 'roll': True, 'stat': stat, 'difficulty': 'normal', 'said': True})
    return actions[:MOST_ACTIONS]


def checked(answer: str) -> list[dict] | None:
    """The model's rolled actions, keeping only well-formed ones; None when nothing in the answer can be read."""
    actions = split(answer)
    return None if actions is None else [action for action in actions if action['roll']]


def split(answer: str) -> list[dict] | None:
    """Every well-formed action in the model's answer, rolled or not; None when nothing in it can be read."""
    match = re.search(r'\{.*\}', answer, re.S)
    try:
        data = json.loads(match.group(0)) if match else None
    except json.JSONDecodeError:
        return None
    items = data.get('actions') if isinstance(data, dict) else None
    if not isinstance(items, list):
        return None
    actions = []
    for item in items[:MOST_ACTIONS]:
        if not isinstance(item, dict) or not str(item.get('action') or '').strip():
            continue
        action = str(item['action']).strip()[:200]
        if item.get('roll') and item.get('stat') in marvel.STATS:
            difficulty = item.get('difficulty') if item.get('difficulty') in marvel.DIFFICULTIES else 'normal'
            actions.append({'action': action, 'roll': True, 'stat': item['stat'], 'difficulty': difficulty})
        elif not item.get('roll'):
            actions.append({'action': action, 'roll': False})
    return actions


def own_model(connection) -> dict | None:
    """The Referee's model, only when the player chose one for the job."""
    return config_for(connection, JOB) if routes(connection).get(JOB) else None


def decision_model(connection) -> dict | None:
    """The model for Referee decisions, only when the player chose one."""
    return config_for(connection, DECISIONS) if routes(connection).get(DECISIONS) else None


def judged(action: str, answers: dict) -> dict:
    """One action decided from a decision model's answers: a roll when it is likely enough, the likeliest stat, and
    the difficulty nearest the expected level."""
    if answers['roll']['probability'] < ROLL_AT:
        return {'action': action, 'roll': False}
    stats = answers['stat']['probabilities']
    level = sum(index * chance for index, chance in enumerate(answers['difficulty']['probabilities']))
    return {'action': action, 'roll': True, 'stat': max(marvel.STATS, key=lambda stat: stats.get(stat, 0)),
            'difficulty': LEVELS[min(len(LEVELS) - 1, max(0, round(level)))]}


async def decided(state, config: dict, actions: list[str], fight: str | None = None) -> list[dict]:
    """Each action's roll, stat and difficulty from the decision model, all asked at once (told of the fight, when
    one is on)."""
    key = key_for(state.vault, config)
    asked = [fight_note(fight) + action if fight else action for action in actions]
    async with state.scheduler.reserve(config, CONVERSATION):
        answers = await asyncio.gather(*(state.decider.ask(config, key, action, QUESTIONS) for action in asked))
    return [judged(action, answer) for action, answer in zip(actions, answers)]


async def decide(state, text: str, config: dict | None, decisions: dict | None = None,
                 fight: str | None = None) -> list[dict]:
    """The rolled actions of one turn: split by the Referee's model when there is one, decided by the decision model
    when there is one, else by the Referee's own answer, else by the keyword rules. `fight` names who the character
    is fighting, when a fight is on, so a line that keeps at them is read as an attack."""
    actions = None
    told = fight_note(fight) + text if fight else text
    if config is not None:
        try:
            async with state.scheduler.reserve(config, CONVERSATION):
                answer = ''.join([chunk.text async for chunk in state.provider.stream(
                    config, key_for(state.vault, config), SYSTEM, [{'role': 'user', 'content': told}])])
        except Exception:  # noqa: BLE001 - a Referee that fails falls back to the rules; the turn goes on.
            answer = ''
        actions = split(answer)
    if decisions is not None and getattr(state, 'decider', None) is not None:
        # Without the Referee's split, each sentence is an action in the player's own words.
        parts = [action['action'] for action in actions] if actions is not None else sentences(text)[:MOST_ACTIONS]
        try:
            judged_actions = await decided(state, decisions, parts, fight)
        except Exception:  # noqa: BLE001 - a decision model that fails falls back too; the turn goes on.
            judged_actions = None
        if judged_actions is not None:
            said = {'said': True} if actions is None else {}
            return armed(text, [{**action, **said} for action in judged_actions if action['roll']], fight)
    if actions is not None:
        return armed(text, [action for action in actions if action['roll']], fight)
    return armed(text, by_keywords(text, fight), fight)


# A blow that is plainly an attack whatever the Referee says, so a fight always starts (dungeon/combat.py stand_in).
VIOLENT = re.compile(r'\b(stab\w*|slash\w*|punch\w*|kick\w*|shoot\w*|attack\w*|kill\w*|hack\w* at|run\w* \w+ '
                     r'through|lunge\w* at|strike\w* at|swing\w* at|cut\w* (at|him|her|them|down)|headbutt\w*|'
                     r'strangl\w*|throttl\w*|hit\w* (him|her|them|the \w+)|club\w* (him|her|them)|smash\w* (him|her|'
                     r'them|the \w+ over)|bash\w* (him|her|them)|brain\w* (him|her|them)|knock\w* (him|her|them) '
                     r'(down|out|cold|senseless))', re.I)
# A line that gives in to the foes (dungeon/combat.py terms decides it): no roll.
GIVING_IN = re.compile(r"\b(hand\w* (it |them |him |her )?over|give (it|them) (up|over)|surrender\w*|yield\w*|"
                       r"give up|beg\w* for (mercy|my life)|hands up|drop\w* my (weapon|sword|axe|knife|blade)|pay "
                       r"(them|him|her) off|(toss|throw|giv|hand|pass|fling|drop)\w*( \w+){0,3}? (purse|money|"
                       r"coins?|silver|valuables))\b", re.I)


def backed(text: str, actions: list[dict], fight: str | None) -> list[dict]:
    """Mid-fight, a line that backs off ("I fall back to the stairs") always rolls Vitality, so the break away
    (dungeon/ranges.py) is decided even when the Referee let it pass unrolled."""
    from dungeon import ranges
    if not fight or any(ranges.backing(action['action']) for action in actions) or len(actions) >= MOST_ACTIONS:
        return actions
    part = next((part for part in sentences(text) if ranges.backing(part)), None)
    return [*actions, {'action': part, 'roll': True, 'stat': 'Vitality', 'difficulty': 'normal', 'said': True}] \
        if part else actions


def armed(text: str, actions: list[dict], fight: str | None = None) -> list[dict]:
    """The rolled actions, with an attack the Referee let pass unrolled added back: a line that attacks someone
    ("I draw my sword and cut down the foreman") always rolls Vitality, so the fight starts, even when the Referee
    called the blow Luck. Giving in to foes (handing over the purse, surrendering) is no feat and rolls nothing."""
    from dungeon import combat
    if fight:
        actions = [action for action in actions if not GIVING_IN.search(action['action'])]
    violent = [index for index, action in enumerate(actions)
               if VIOLENT.search(action['action']) and (fight or combat.SOMEONE.search(action['action']))]
    if violent and not any(action.get('stat') == 'Vitality' for action in actions):
        actions = [action | {'stat': 'Vitality'} if index == violent[0] else action
                   for index, action in enumerate(actions)]
    actions = backed(text, actions, fight)
    if any(action.get('stat') == 'Vitality' for action in actions) or len(actions) >= MOST_ACTIONS:
        return actions
    for part in sentences(text):
        if VIOLENT.search(part) and (fight or combat.SOMEONE.search(part)):
            return [*actions, {'action': part, 'roll': True, 'stat': 'Vitality', 'difficulty': 'normal',
                               'said': True}]
    return actions
