"""The Table: this campaign's rules (docs/story.md "The Table").

Settings follow the user from world to world (dungeon/restore.py KEPT_SETTINGS), so rules kept there leaked: turn the
dice on in one campaign and they were on in every other. The Table keeps them with the campaign (story_campaign), so
each world's campaign plays by its own.

- **Tone** (intensity, drama, injury_persistence, defeat, levels, veils, voice) is the world's at the start of every
  campaign: 'world' for the dials and the voice, no categories moved off the preset, the world's veils, permanent
  injuries, a 5E defeat as written (death saves), shopkeepers with finite cash, carrying limited by slots, and the
  world's own clock (story time, or real time for a world that lives that way), rule text for the narrator
  (dungeon/rules/passages.py), anyone with a reason able to stop the character leaving (dungeon/leaving.py), and local politics true to life
  (dungeon/politics.py). Picking a preset clears the categories moved off it.
- **Narration format** (pov, tense, length) is the player's at any time. A new campaign starts in close third person,
  past tense (requirements "Narrator prompting": the default for a persona); a story with no campaign start, or a
  campaign from before the format could be chosen, keeps second person and present tense, as Story mode always had.
- **Display taste** (show_odds, roll_dice, show_adult_side, gm_view, cutaways) starts where the player last left it,
  which the workspace settings remember.

Either route sets a rule for the campaign being played: PUT /story/table, or PUT /settings (scripts and older callers).
Both also remember the choice in the workspace settings, which a new campaign's taste starts from. story.clear wipes
story_campaign, so a new story begins with a fresh table. Not in timeline.SAVED: a rule changed and then a line rewound
stays changed.
"""
from dungeon.database import decode, encode, optional, settings

TONE = {'intensity': 'world', 'drama': 'world', 'injury_persistence': 'permanent', 'defeat': 'as_written',
        'levels': None, 'veils': None, 'voice': 'world', 'shop_cash': 'finite',
        'carry_limit': 'slots', 'clock': 'world', 'rule_text': 'on', 'leaving': 'anyone',
        'politics': 'true_to_life'}
# Kept as JSON: the categories the player moved off the preset (dungeon/tone.py), and the veiled topics (None: the
# world's own).
JSON_RULES = ('levels', 'veils')
# The narration format (dungeon/narration/prompt.py Format): what a story with no campaign, or an older campaign, is
# told in, and what a new campaign starts in.
FORMAT = {'pov': 'second', 'tense': 'present', 'length': 'short'}
NEW_FORMAT = {'pov': 'third', 'tense': 'past', 'length': 'short'}
TASTE = ('show_odds', 'roll_dice', 'show_adult_side', 'gm_view', 'cutaways')
RULES = (*TONE, *FORMAT, *TASTE)

# Session zero's presets: each sets the tone and the director's hand ('world' and None are the world's own). The world's
# own comes first and is picked unless the player picks another; a world bible may name its own presets later.
PRESETS = (
    {'id': 'as-written', 'name': 'As the world is written', 'hand': None,
     'about': "The world's own tone and trouble. Wounds can last.",
     'rules': {'intensity': 'world', 'drama': 'world', 'injury_persistence': 'permanent'}},
    {'id': 'gentler', 'name': 'Gentler', 'hand': 'soft',
     'about': 'Less on the page, fewer troubles, and wounds that fade. The story waits for you.',
     'rules': {'intensity': 'restrained', 'drama': 'quiet', 'injury_persistence': 'temporary'}},
    {'id': 'harsher', 'name': 'Harsher', 'hand': 'firm',
     'about': 'Nothing held back, trouble often and at its worst, and wounds that stay. The story moves on schedule.',
     'rules': {'intensity': 'unflinching', 'drama': 'merciless', 'injury_persistence': 'permanent'}},
)
FLAGS = set(TASTE)


def stored(connection) -> dict:
    row = optional(connection, f'SELECT {", ".join(RULES)} FROM story_campaign WHERE id=1')
    return row or dict.fromkeys(RULES)


def rules(connection) -> dict:
    """Each rule as the campaign sets it; one it has not set yet is the world's tone or the player's last taste."""
    row, last = stored(connection), settings(connection)
    fallback = TONE | FORMAT | {key: last[key] for key in TASTE}
    found = {key: (bool(value) if key in FLAGS else value)
             for key, value in ((key, fallback[key] if row[key] is None else row[key]) for key in RULES)}
    return found | {key: decode(found[key]) if isinstance(found[key], str) else found[key] for key in JSON_RULES}


def rule(connection, key: str):
    return rules(connection)[key]


def change(connection, changes: dict):
    """Sets rules for this campaign; taste is remembered for the next one too."""
    chosen = {key: int(value) if isinstance(value, bool) else encode(value) if key in JSON_RULES and value is not None
              else value for key, value in changes.items() if key in RULES}
    if not chosen:
        return
    columns = ', '.join(chosen)
    connection.execute(f'INSERT INTO story_campaign (id, {columns}) VALUES (1, {", ".join("?" * len(chosen))}) '
                       f'ON CONFLICT(id) DO UPDATE SET {", ".join(f"{key}=excluded.{key}" for key in chosen)}',
                       tuple(chosen.values()))


def choose(connection, changes: dict, now: str):
    """The player sets rules at the table: this campaign's, with taste remembered for the next campaign. A preset
    picked sets every category again."""
    if 'intensity' in changes and 'levels' not in changes:
        changes = changes | {'levels': {}}
    change(connection, changes)
    taste = {key: int(value) for key, value in changes.items() if key in FLAGS}
    if taste:
        columns = ', '.join(f'{key}=?' for key in taste)
        connection.execute(f'UPDATE workspace_settings SET {columns}, updated_at=? WHERE id=1', (*taste.values(), now))


def starting(connection) -> dict:
    """The rules a new campaign would start with, before it begins: the format a new campaign starts in."""
    unset = {key for key, value in stored(connection).items() if value is None}
    return {key: NEW_FORMAT[key] if key in unset and key in NEW_FORMAT else value for key, value in rules(connection).items()}


def begin(connection):
    """Sets the table for a new campaign: every rule the player did not already set before it began."""
    unset = {key for key, value in stored(connection).items() if value is None}
    change(connection, {key: value for key, value in (rules(connection) | NEW_FORMAT).items() if key in unset})


def adopt(connection):
    """A campaign from before the Table played by the workspace's rules; it keeps them as its own. Plain SQL, as it
    runs while the database is set up (dungeon/database.py initialize), on any connection."""
    unset = ' AND '.join(f'{key} IS NULL' for key in (*TONE, *TASTE))
    kept = ', '.join(f'{key}=(SELECT {key} FROM workspace_settings WHERE id=1)' for key in (*TONE, *TASTE))
    connection.execute(f'UPDATE story_campaign SET {kept} WHERE id=1 AND {unset}')
