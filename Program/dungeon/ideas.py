"""Ideas: two or three things the character could do now, when the player asks (requirements "Suggested actions";
docs/story.md "Ideas").

Ideas are used once and thrown away. Nothing here writes to the database: the list goes back in the response and
lives only in the browser's memory until the player sends a line, asks again or the story moves. So no narrator,
Referee, extractor, summary, recall, director or picture prompt can ever read one, and the next Ideas call is built
fresh from the scene, never from the last list. An idea the player picks and sends is their own line from then on,
like anything else they type; the ones they did not pick go nowhere.

The prompt holds only what the character knows: the scene as the screen shows it (never the names of people they have
not met), what the record says they know, the quests and threads they have come across as they understand them, who
they are, and the last few lines. Never hidden truth, the director's note, off-page beats or secrets. It asks for
actions in the player's words, never results, rolls or odds, within the player's intensity levels and veils.

The Referee's model writes them when one is chosen, else the story's. With no model, or an answer that cannot be read,
code offers some from the scene: talk to someone here, browse the open shop, rest when hurt, head somewhere nearby.
"""
import json
import re

from dungeon import director, injuries, quests, record, referee, story, story_clock, tone
from dungeon.text_models import config_for

MOST = 3
MOST_WORDS = 20
RECENT_LINES = 3
MOST_KNOWN = 12
# Words that make an idea a result rather than an action, so it is dropped.
RESULT = re.compile(r'\b(succeed\w*|fail\w*|roll\w*|odds|chance of|dice|critical\w*|you (find|discover|learn) that)\b',
                    re.I)

SYSTEM = """You suggest what a player's character could do next in a tabletop roleplaying game for adults.

Give exactly three short actions the player might write, each in the first person ("I ask...", "I slip..."), each
under twenty words: one social, one physical or risky, one cautious or clever. Use only what is in the scene and what
the character knows below. Never say how an action turns out: no results, no rolls, no odds. Name no one the scene
does not name. Stay within the content limits below.

Answer with a JSON list of three strings and nothing else."""


def known_scene(connection, database) -> dict:
    """What the character can see and knows right now, for the prompt and the fallback: nothing hidden."""
    view = story.scene(connection, story_clock.now(connection, database.clock))
    seen = story.scene_view(view)
    persona, name = story.persona_text(connection)
    return {'scene': seen, 'persona': persona, 'name': name,
            'shop': story.shop_view(connection, view),
            'known': [f"{row['subject']}: {row['text']}" for row in record.entries(connection, known_only=True)
                      if not row['faded']][:MOST_KNOWN],
            'quests': [f"{quest['title']}: {quest['hook']}" for quest in quests.view(connection, view['now'])
                       if quest['status'] == 'open'],
            'threads': [thread['title'] for thread in director.journal(connection)],
            'hurt': bool(injuries.view(connection, view['now'])),
            'recent': [row['text'] for row in story.messages(connection, RECENT_LINES * 2)][-RECENT_LINES:],
            'limits': tone.narration(story.intensity(connection, view['data'])).text(),
            'turn': len(story.messages(connection))}


def prompt(known: dict) -> str:
    """The one user message of the Ideas call: built fresh every time, never from an earlier list."""
    scene = known['scene']
    lines = [f"Place: {scene['place']['name']}, a {scene['place']['kind']} in {scene['place']['neighborhood']}, "
             f"{scene['city']['name']}. {scene['place'].get('summary', '')}".strip()]
    if scene.get('weather'):
        lines.append(f"Weather: {scene['weather']}")
    lines.append('People here: ' + ('; '.join(scene['around']) if scene['around'] else 'nobody the story knows'))
    if known['shop']:
        lines.append('There is a shop here' + (', open.' if known['shop'].get('open') else ', closed.'))
    if known['persona']:
        lines.append(f"The character:\n{known['persona']}")
    for title, items in (('What the character knows', known['known']), ('Their open quests', known['quests']),
                         ('Threads they have come across', known['threads'])):
        if items:
            lines.append(f'{title}:\n' + '\n'.join(f'- {item}' for item in items))
    if known['recent']:
        lines.append('The last lines of the story:\n' + '\n\n'.join(known['recent']))
    if known['limits']:
        lines.append(f"Content limits:\n{known['limits']}")
    return '\n\n'.join(lines)


def parse(answer: str) -> list[str]:
    """At most three ideas from the model's answer: actions only, none too long, no repeats."""
    found = re.search(r'\[.*\]', answer, re.S)
    try:
        items = json.loads(found.group(0)) if found else []
    except ValueError:
        items = []
    ideas = []
    for item in items if isinstance(items, list) else []:
        text = re.sub(r'\s+', ' ', item).strip().strip('"') if isinstance(item, str) else ''
        if text and len(text.split()) <= MOST_WORDS and not RESULT.search(text) and text not in ideas:
            ideas.append(text)
    return ideas[:MOST]


def fallback(known: dict) -> list[str]:
    """Ideas from the scene alone, when no model can write them."""
    scene, ideas = known['scene'], []
    if scene['around']:
        ideas.append(f"I strike up a conversation with {scene['around'][0]}.")
    if known['shop'] and known['shop'].get('open'):
        ideas.append('I look over what is for sale.')
    if known['hurt']:
        ideas.append('I find somewhere to rest and see to my wounds.')
    if known['quests']:
        ideas.append(f"I ask around about {known['quests'][0].split(':')[0]}.")
    nearby = [place['name'] for place in scene.get('places', []) if place['id'] != scene['place']['id']]
    if nearby:
        ideas.append(f'I head over to {nearby[0]}.')
    ideas.append('I take a careful look around.')
    return ideas[:MOST]


def model(connection) -> dict | None:
    """The Referee's model when one is chosen, else the story's."""
    return referee.own_model(connection) or config_for(connection, story.JOB)


async def ideas(state, database) -> dict:
    """Two or three ideas for this moment, and the turn they were made for, so a stale list can be dropped."""
    with database.connect() as connection:
        known, config = known_scene(connection, database), model(connection)
    found = []
    if config is not None:
        try:
            found = parse(await story.complete(state, config, SYSTEM, [{'role': 'user', 'content': prompt(known)}]))
        except Exception:  # noqa: BLE001 - a model that fails leaves the scene's own ideas.
            found = []
    return {'ideas': found if len(found) >= 2 else fallback(known), 'turn': known['turn']}
