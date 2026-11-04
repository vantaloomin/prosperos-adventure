"""Request bodies. Input mirrors prosperos-study server/models.py at bbcbde4."""
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Relationship = Literal['friendship', 'romance', 'mentor', 'family', 'other']
Layer = Literal['user_fact', 'shared_experience', 'plan', 'temporary', 'relationship', 'companion_life']
PlanStatus = Literal['proposed', 'agreed', 'postponed', 'cancelled', 'completed']
EventKind = Literal['routine', 'plan', 'ordinary', 'thread']
BlockKind = Literal['work', 'study', 'errand', 'leisure', 'social', 'rest', 'sleep']
ClockTime = Annotated[str, Field(pattern=r'^([01][0-9]|2[0-3]):[0-5][0-9]$')]
Intensity = Literal['mild', 'moderate', 'strong']


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class Looks(Input):
    """What they look like, field by field (adventure/world/looks.py); an empty field is drawn for them."""
    age: int | None = Field(default=None, ge=18, le=120)
    height_cm: int | None = Field(default=None, ge=120, le=230)
    weight_kg: int | None = Field(default=None, ge=35, le=250)
    build: str = Field(default='', max_length=120)
    skin: str = Field(default='', max_length=120)
    face: str = Field(default='', max_length=120)
    jaw: str = Field(default='', max_length=120)
    nose: str = Field(default='', max_length=120)
    eyes: str = Field(default='', max_length=120)
    eye_shape: str = Field(default='', max_length=120)
    hair: str = Field(default='', max_length=200)
    facial_hair: str = Field(default='', max_length=120)
    feature: str = Field(default='', max_length=200)
    # The values the app filled in when a townsperson became a companion (adventure/cast.py): a field still equal to
    # its drawn value is the app's, so it may change over time (adventure/life/grooming.py); one the user edited is not.
    drawn: dict[str, int | str] = Field(default_factory=dict, max_length=20)


PersonalityTrait = Literal['social', 'warmth', 'order', 'curiosity', 'stress']


DraftField = Literal['identity', 'personality', 'voice', 'skills', 'flaws', 'interests', 'background', 'appearance',
                     'routine', 'life_themes', 'schedule']


class LoreFile(Input):
    """A lorebook file (JSON or .lorebook), base64 encoded (adventure/lore.py)."""
    filename: str = Field(min_length=1, max_length=260)
    data: str = Field(min_length=1, max_length=14_000_000)


class LibraryFile(Input):
    """A long text for the reference library (adventure/library.py), base64 encoded."""
    filename: str = Field(min_length=1, max_length=260)
    data: str = Field(min_length=1, max_length=14_000_000)


class LoreSwitch(Input):
    """Turn an imported lorebook, or one of its entries, on or off (adventure/lore.py)."""
    enabled: bool


class LoreEntryNew(Input):
    """A lore entry of the user's own (adventure/lore.py `add_entry`), public or GM only."""
    title: str = Field('', max_length=200)
    text: str = Field(min_length=1, max_length=4000)
    keywords: list[str] = Field(default_factory=list, max_length=20)
    always: bool = False
    visibility: str = Field('public', max_length=10)


class LoreVisibility(Input):
    """Who may read a lore entry (adventure/lore.py "Who may read it"): public, known (to `known_to`, character keys)
    or gm; checked there."""
    visibility: str = Field(max_length=10)
    known_to: list[str] = Field(default_factory=list, max_length=40)


class LoreTiming(Input):
    """A lore entry's timing (adventure/lore.py TIMING), in story lines; the ranges are checked there."""
    sticky: int | None = None
    cooldown: int | None = None
    delay: int | None = None
    chance: int | None = None
    group_weight: int | None = None
    group: str | None = Field(None, max_length=80)


class LoreWhen(Input):
    """When a lore entry applies besides its keywords (adventure/lore_moments.py): conditions such as "weather:rain"."""
    when: list[Annotated[str, Field(max_length=160)]] = Field(max_length=40)


class PromptUpdate(Input):
    text: str = Field(min_length=1, max_length=20000)


HEX = r'^#[0-9a-fA-F]{6}$'


class Palette(Input):
    """A custom color scheme, as Prospero's Study's custom palette."""
    accent: str = Field(pattern=HEX)
    background: str = Field(pattern=HEX)
    surface: str = Field(pattern=HEX)
    text: str = Field(pattern=HEX)


class SettingsUpdate(Input):
    user_timezone: str | None = Field(default=None, max_length=64)
    # 'detected': the interface reporting this PC's zone; 'pc': Use this PC's timezone; otherwise chosen.
    user_timezone_source: Literal['detected', 'pc', 'chosen'] | None = None
    color_scheme: Literal['ink', 'slate', 'umber', 'moss', 'wine', 'ash', 'custom'] | None = None
    custom_palette: Palette | None = None
    # 'system' matches the computer (Paper or Ink), 'paper' is the light profile, 'scheme' uses color_scheme.
    theme: Literal['system', 'scheme', 'paper'] | None = None
    show_odds: bool | None = None
    # The adult side of life (adventure/world/intimacy.py) and whether townsfolk's shows.
    adult_side: bool | None = None
    show_adult_side: bool | None = None
    # Automatic backups of every world (adventure/auto_backup.py).
    auto_backups: Literal['off', 'daily', 'weekly'] | None = None
    # How far the story goes on the page: the world's preset, or one the player chose (adventure/story.py intensity).
    intensity: Literal['world', 'restrained', 'mature', 'unflinching'] | None = None
    # Seconds a story turn may take before its optional steps give way (adventure/pace.py); 0 is automatic.
    turn_budget: Literal[0, 15, 30, 60, 90, 120, 180] | None = None
    # How eventful the story is (adventure/happenings.py): the world's own level, or the player's.
    drama: Literal['world', 'quiet', 'uneasy', 'eventful', 'merciless'] | None = None
    # Short "meanwhile" cutaways of off-page beats for the player (adventure/beats.py).
    cutaways: bool | None = None
    # Dice that tumble on screen and land on the code's roll, while the dice are shown.
    roll_dice: bool | None = None
    # The GM view of the record (adventure/record.py): hidden truth shown and editable.
    gm_view: bool | None = None
    # Rewrite a narration that clashes with the record before it is shown (off is faster on slow local models).
    contradiction_check: bool | None = None
    # Pictures made on their own from what happens in the story (adventure/art.py passive).
    passive_art: bool | None = None
    # Tokens a turn may send at most (adventure/remembering.py); 0 is the model's whole window.
    context_cap: Literal[0, 4000, 8000, 16000, 32000, 64000] | None = None
    # Injury persistence (adventure/injuries.py): lasting injuries stay, fade, or never happen.
    injury_persistence: Literal['permanent', 'temporary', 'none'] | None = None
    # The first-run notice: the story is AI written, and the user is 18 or older. Only ever confirmed.
    ai_notice_confirmed: Literal[True] | None = None


class ConnectionUpdate(Input):
    base_url: str = Field(min_length=1, max_length=500)
    model: str = Field(min_length=1, max_length=200)
    api_key: str | None = Field(default=None, max_length=4000)
    max_output_tokens: int = Field(default=800, ge=64, le=128000)
    context_tokens: int = Field(default=16000, ge=1024, le=2000000)
    timeout_seconds: int = Field(default=180, ge=10, le=1800)
    # Optional embedding model on the same connection; empty keeps recall keyword-only.
    embedding_model: str | None = Field(default=None, max_length=200)


Gender = Literal['woman', 'man', 'nonbinary', '']
Birthday = Annotated[str, Field(pattern=r'^(?:(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01]))?$')]


# Lifespans (adventure/world/lifespans.py `SPANS`): what How long they live offers, besides as their kind.
LIFESPANS = (80, 150, 300, 600, 1000)
# A persona's age: up to 120, and up to 5,000 for a long-lived kind (adventure/worlds.py).
PERSONA_AGES = (120, 5000)


class PersonaInput(Input):
    """Who the user is in a persona's worlds (adventure/worlds.py). Only the user says this; blanks stay blank."""
    name: str | None = Field(None, max_length=80)
    gender: Gender | None = None
    # Past 120 only for a long-lived kind, picked below or read from About you (adventure/worlds.py checks it).
    age: int | None = Field(None, ge=18, le=PERSONA_AGES[1])
    about: str | None = Field(None, max_length=2000)
    birthday: Birthday | None = None
    # Kind and How long they live (adventure/world/lifespans.py), as on the Character page: '' and None leave both to
    # their words, 0 years is "Doesn't age".
    kind: str | None = Field(None, max_length=40, pattern=r'^[a-z0-9-]*$')
    lifespan: int | None = None

    @field_validator('lifespan')
    @classmethod
    def listed(cls, value):
        if value not in (None, 0, *LIFESPANS):
            raise ValueError('Pick one of the lifespans listed.')
        return value


class MadeSlider(Input):
    """One personality slider (adventure/world/personality.py): its stop and who set it."""
    level: int = Field(ge=0, le=2)
    source: Literal['rolled', 'idea', 'you'] = 'you'


class MadeLooks(Input):
    """Looks (adventure/world/looks.py): each field optional, a blank one drawn for them."""
    age: int | None = Field(None, ge=18, le=PERSONA_AGES[1])
    height_cm: int | None = Field(None, ge=100, le=250)
    weight_kg: int | None = Field(None, ge=30, le=300)
    build: str = Field('', max_length=120)
    skin: str = Field('', max_length=120)
    face: str = Field('', max_length=120)
    jaw: str = Field('', max_length=120)
    nose: str = Field('', max_length=120)
    eyes: str = Field('', max_length=120)
    eye_shape: str = Field('', max_length=120)
    hair: str = Field('', max_length=200)
    facial_hair: str = Field('', max_length=120)
    feature: str = Field('', max_length=200)


class MadeCharacter(Input):
    """A character the player makes on the cast page (adventure/making.py), beyond the persona's name, gender, age and
    About you: their look, voice, wants and fears, personality sliders, Looks and how they come across. `seed` rolls
    whatever is left open, so the form and Begin roll the same."""
    seed: str = Field('', max_length=80, pattern=r'^[A-Za-z0-9-]*$')
    look: str = Field('', max_length=600)
    voice: str = Field('', max_length=600)
    wants: str = Field('', max_length=300)
    fears: str = Field('', max_length=300)
    personality_sliders: dict[Literal['social', 'warmth', 'order', 'curiosity', 'stress'], MadeSlider] | None = None
    looks: MadeLooks | None = None
    seen_as: str = Field('', max_length=400)
    sees_self: str = Field('', max_length=1200)


class MadeForm(MadeCharacter):
    """The cast page's form as it stands, for the sliders, Looks and perception it rolls; `roll` rolls the Rolled
    sliders again."""
    name: str = Field('', max_length=80)
    gender: Gender = ''
    age: int | None = Field(None, ge=18, le=PERSONA_AGES[1])
    about: str = Field('', max_length=2000)
    roll: int | None = Field(None, ge=1, le=1_000_000)


class MadePicks(Input):
    """What the quick start sends the model to draft from (adventure/making.py `draft`): anything left open is
    the model's to choose."""
    name: str = Field('', max_length=80)
    gender: Gender = ''
    age: int | None = Field(None, ge=18, le=PERSONA_AGES[0])
    idea: str = Field('', max_length=2000)


class MadePaste(Input):
    """A character the player already has, pasted whole, for the model to split into the fields."""
    text: str = Field(min_length=1, max_length=40000)


class CharacterFile(Input):
    """A character file from another app, base64 encoded (adventure/imports/formats.py)."""
    filename: str = Field(min_length=1, max_length=260)
    data: str = Field(min_length=1, max_length=14_000_000)


class NewPersona(PersonaInput):
    """A new persona, and the city their world is in: the current one unless the user picks another, or
    `somewhere-new` for the app to pick, or `somewhere-new:<world>` for it to pick in that world (adventure/worlds.py)."""
    city_id: str | None = Field(None, min_length=1, max_length=120)


class HomeChange(Input):
    """Where the user lives in a world (adventure/life/where.py): a city and a neighbourhood there; a blank
    neighbourhood lets the app pick one."""
    city_id: str = Field(min_length=1, max_length=120)
    neighbourhood: str = Field(default='', max_length=120)


class WorldChange(Input):
    """Rename a world, or give it to another persona."""
    name: str | None = Field(None, max_length=80)
    persona_id: str | None = Field(None, min_length=1, max_length=100)


class NewWorld(Input):
    """A new world: for the active persona and in the current city unless these say otherwise."""
    persona_id: str | None = Field(None, min_length=1, max_length=100)
    name: str | None = Field(None, max_length=80)
    city_id: str | None = Field(None, min_length=1, max_length=120)


