"""The other leads join as the party at Begin (the cast page's "Join as your party").

A city's premade characters (adventure/campaign.py `premades`) are its leads. When the story begins with a `party`,
every lead the player did not choose travels with their character from the first line (adventure/party.py), is met
(adventure/story_people.py), and takes a round seat (adventure/rounds/seats.py) with the mind the cast page set:
'agent' (Thinks) or 'program' (Rules). The player's own character is the human seat, `HUMAN`. Begun without a
party, the story plays exactly as before.

Each lead's seat key is their premade id, which is also their id in the world package, so what the package says
they know reaches them (adventure/rounds/context.py `package_ids`). Their sheet is drawn the way a package's notable
is (adventure/world/townsfolk.py), at the place the story opens, with the premade's name, age and description.
"""
from datetime import date

from adventure import story_people, world_data
from adventure.database import encode
from adventure.errors import require
from adventure.rounds import seats
from adventure.rounds.contract import Mind
from adventure.world import catalog, townsfolk

HUMAN = 'you'
PRONOUNS = {'woman': 'she/her', 'man': 'he/him'}
ROLE_CHARS, WANTS_CHARS = 80, 200


def personas(world: str | None) -> set[str]:
    """The ids of the world package's playable personas."""
    from adventure import package_lore, packages
    if not world:
        return set()
    held = world_data.sections(world, package_lore.CHARACTERS).get('personas') or {}
    return {entry.get('id') for entry in held.get(packages.SECTIONS['personas']) or [] if isinstance(entry, dict)}


def default_mind(world: str | None, premade: dict) -> str:
    """How a lead plays when the cast page leaves it alone: the premade's own `mind` when it gives one, else a
    playable persona thinks for themselves (an agent) and anyone else runs on the game's rules."""
    if premade.get('mind') in (Mind.AGENT, Mind.PROGRAM):
        return premade['mind']
    return Mind.AGENT if premade['id'] in personas(world) else Mind.PROGRAM


def first_text(value) -> str:
    return str(value[0] if isinstance(value, list) and value else value or '')


def sheet_for(data: dict, place_id: str, premade: dict, world: str | None) -> dict:
    """A lead's townsfolk sheet: drawn as a notable at the place the story opens, keyed by their premade id."""
    entry = world_data.person(world, premade['id']) or {}
    role = first_text(entry.get('role')) or 'travelling companion'
    notable = {'id': premade['id'], 'name': premade['name'], 'pronouns': PRONOUNS.get(premade.get('gender'), 'they/them'),
               'age': max(16, int(premade.get('age') or 30)), 'place': place_id, 'role': role[:ROLE_CHARS],
               'staff': False, 'about': premade.get('about', ''), 'wants': first_text(entry.get('wants'))[:WANTS_CHARS],
               'source': world or data['id']}
    place = catalog.find(data, place_id)
    held = data | {'notables': [*townsfolk.notables_at(data, place_id), notable]}
    index = townsfolk.everyone(held, place) - 1
    drawn = townsfolk.person(held, place, index)
    return drawn | {'key': premade['id'], 'cast': premade['id']}


def checked(leads: list[dict], chosen_id: str | None, chosen: dict) -> dict[str, dict]:
    """The cast page's choices, each lead's own: every lead but the player's, with a known mind."""
    others = {lead['id'] for lead in leads if lead['id'] != chosen_id}
    unknown = set(chosen) - others
    require(not unknown, f"Not a lead who can join: {', '.join(sorted(unknown))}.", 422)
    for choice in chosen.values():
        require(choice.get('mind') in (None, Mind.AGENT, Mind.PROGRAM), 'A lead thinks (agent) or rules (program).',
                422)
    return {key: chosen.get(key) or {} for key in sorted(others, key=[lead['id'] for lead in leads].index)}


def join(connection, data: dict, place_id: str, leads: list[dict], chosen_id: str | None, player: str,
         chosen: dict, world: str | None, now: str, day: date):
    """Every lead but the player's joins the party and the table; the player sits as the human."""
    choices = checked(leads, chosen_id, chosen)
    by_id = {lead['id']: lead for lead in leads}
    seats.set_seat(connection, HUMAN, player, now, mind=Mind.HUMAN)
    for key, choice in choices.items():
        lead = by_id[key]
        sheet = sheet_for(data, place_id, lead, world)
        story_people.meet(connection, sheet, data['id'], now, day)
        connection.execute('INSERT OR REPLACE INTO story_party (key, name, city_id, sheet, joined) VALUES '
                           '(?, ?, ?, ?, ?)', (key, sheet['full'], data['id'], encode(sheet), now))
        seats.set_seat(connection, key, sheet['full'], now, mind=choice.get('mind') or default_mind(world, lead),
                       notes=choice.get('notes') or '', model_profile_id=choice.get('model_profile_id'))


def begin(connection, database, city_id: str, leads: list[dict], chosen_id: str | None, player: str,
          chosen: dict | None):
    """At Begin (adventure/campaign.py): the party joins when the cast page sent one; with none, nothing changes."""
    from adventure import story, story_clock, tiers
    if chosen is None:
        return
    data = story.city_data(connection, city_id)
    day = story.local_moment(data, story_clock.now(connection, database.clock)).date()
    join(connection, data, story.scene_row(connection)['place_id'], leads, chosen_id, player, chosen,
         tiers.world_of(city_id), database.now(), day)
