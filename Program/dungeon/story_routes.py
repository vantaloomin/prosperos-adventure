"""The story API (dungeon/story.py, docs/story.md)."""
import asyncio
import json
from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import Field

from dungeon import (
    art,
    book,
    campaign,
    chapters,
    dice_log,
    director,
    gm,
    growth,
    happenings,
    icons,
    ideas,
    institutions,
    legacy,
    plotting,
    quests,
    record,
    sheet,
    story,
    story_clock,
    table,
    tiers,
    townmap,
    world_select,
    world_theme,
)
from dungeon.errors import DomainError, require
from dungeon.models import Input, PersonaInput

router = APIRouter(prefix='/api/story')


class StoryMessage(Input):
    text: str = Field(min_length=1, max_length=40000)
    client_id: str = Field(min_length=8, max_length=100)


class StoryScene(Input):
    city_id: str = Field(min_length=1, max_length=80)
    place_id: str | None = Field(None, min_length=1, max_length=80)


@router.get('')
def read(request: Request):
    return story.story(request.app.state.database)


@router.put('/scene')
def move(request: Request, body: StoryScene):
    return story.move(request.app.state.database, body.city_id, body.place_id)


class StoryPerson(Input):
    key: str = Field(min_length=1, max_length=200)


@router.post('/find')
def find(request: Request, body: StoryPerson):
    return story.find(request.app.state.database, body.key)


@router.post('/messages')
async def send(request: Request, body: StoryMessage, background: BackgroundTasks):
    result = await story.send(request.app.state, body.text, body.client_id)
    background.add_task(story.settled, request.app.state)
    return result


@router.post('/retry')
async def retry(request: Request, background: BackgroundTasks):
    result = await story.retry(request.app.state)
    background.add_task(story.settled, request.app.state)
    return result


class StoryRewrite(Input):
    passage: str = Field(min_length=1, max_length=20000)
    note: str = Field('', max_length=300)


@router.post('/ideas')
async def suggest(request: Request):
    """Two or three things the character could do now (dungeon/ideas.py). Used once: nothing is stored."""
    return await ideas.ideas(request.app.state, request.app.state.database)


@router.post('/messages/{message_id}/rewrite')
async def rewrite(request: Request, message_id: str, body: StoryRewrite, background: BackgroundTasks):
    result = await story.rewritten(request.app.state, message_id, body.passage, body.note)
    background.add_task(story.settled, request.app.state)
    return result


@router.post('/messages/{message_id}/switch')
async def switch_wording(request: Request, message_id: str, background: BackgroundTasks):
    result = await story.switched(request.app.state, message_id)
    background.add_task(story.settled, request.app.state)
    return result


def streamed(state, start) -> StreamingResponse:
    """A turn as newline-delimited JSON: the turn's stages as they happen ({"stage": "reading"}, {"actions": [...]}
    and one {"roll": {...}} each, {"stage": "writing"}; dungeon/story.py `answer`), {"text": piece} as the narration
    is written, then {"done": result} once the reply is saved (or {"error": message, "status": n}). Fact extraction
    runs after "done" (dungeon/pace.py)."""
    pieces: asyncio.Queue = asyncio.Queue()

    async def on_text(piece: str):
        await pieces.put({'text': piece})

    async def run():
        try:
            await pieces.put({'done': await start(on_text, pieces.put)})
        except DomainError as failure:
            await pieces.put({'error': failure.message, 'code': failure.code, 'status': failure.status})
        finally:
            await pieces.put(None)

    async def lines():
        task = asyncio.ensure_future(run())
        while (item := await pieces.get()) is not None:
            yield json.dumps(item, ensure_ascii=False) + '\n'
        await task
        await story.settled(state)

    return StreamingResponse(lines(), media_type='application/x-ndjson')


@router.post('/messages/stream')
async def send_streamed(request: Request, body: StoryMessage):
    state = request.app.state
    return streamed(state, lambda on_text, on_event: story.send(state, body.text, body.client_id, on_text, on_event))


@router.post('/retry/stream')
async def retry_streamed(request: Request):
    state = request.app.state
    return streamed(state, lambda on_text, on_event: story.retry(state, on_text, on_event))


class SheetChange(Input):
    stats: dict[str, int]


@router.get('/sheet')
def read_sheet(request: Request):
    with request.app.state.database.connect() as connection:
        return sheet.full_view(connection) | {'growth': growth.view(connection, story.dice_shown(connection))}


@router.get('/town')
def read_town(request: Request):
    """The street map of the town the story is in (dungeon/townmap.py), or null between towns."""
    with request.app.state.database.connect() as connection:
        return {'town': townmap.view(connection)}


@router.post('/town/lots/{lot_id}/look')
def look_at_lot(request: Request, lot_id: str):
    """Look at a blank building on the town map: what stands there is decided now and kept."""
    with request.app.state.database.connect(write=True) as connection:
        found = townmap.look(connection, lot_id)
        return {'found': found, 'town': townmap.view(connection)}


@router.put('/sheet')
def change_sheet(request: Request, body: SheetChange):
    database = request.app.state.database
    with database.connect(write=True) as connection:
        require(sheet.ruleset(connection) == 'marvel', "This ruleset's sheet is set when the character is made.", 409)
        sheet.set_stats(connection, body.stats, database.now())
        return sheet.full_view(connection) | {'growth': growth.view(connection, story.dice_shown(connection))}


class LegacyChoice(Input):
    """Another world's story brought in as history (dungeon/legacy.py)."""
    world_id: str = Field(min_length=1, max_length=80)
    role: Literal['legend', 'villain', 'corpse']


class Srd52Build(Input):
    """A 5E character (dungeon/rules/srd52.py build): pack ids, the standard array placed, the class's skills."""
    class_id: str = Field(min_length=1, max_length=80)
    species_id: str = Field(min_length=1, max_length=80)
    background_id: str = Field(min_length=1, max_length=80)
    scores: dict[str, int]
    skills: list[str] = Field(default_factory=list, max_length=8)


class TableUpdate(Input):
    """The Table (dungeon/table.py): this campaign's rules."""
    intensity: Literal['world', 'restrained', 'mature', 'unflinching'] | None = None
    drama: Literal['world', 'quiet', 'uneasy', 'eventful', 'merciless'] | None = None
    injury_persistence: Literal['permanent', 'temporary', 'none'] | None = None
    show_odds: bool | None = None
    roll_dice: bool | None = None
    show_adult_side: bool | None = None
    gm_view: bool | None = None
    cutaways: bool | None = None
    defeat: Literal['as_written', 'by_aim'] | None = None
    # dungeon/tone.py: categories moved off the preset (0 off the page to 3 unflinching), veiled topics, the voice.
    levels: dict[Literal['violence', 'sex', 'horror', 'cruelty', 'drugs'], Annotated[int, Field(ge=0, le=3)]] | None = None
    veils: list[Literal['execution', 'slavery', 'mutilation', 'disease', 'self-harm', 'addiction', 'torture',
                        'sexual-violence', 'sacrifice', 'child-harm']] | None = Field(default=None, max_length=10)
    voice: Literal['world', 'grim', 'wry', 'romantic', 'hopeful', 'lyrical', 'plain'] | None = None
    # The narration format (dungeon/narration/prompt.py Format).
    pov: Literal['first', 'second', 'third'] | None = None
    tense: Literal['past', 'present'] | None = None
    length: Literal['short', 'medium', 'long'] | None = None
    # Whether shopkeepers have finite cash (dungeon/inventory.py).
    shop_cash: Literal['finite', 'unlimited'] | None = None
    # Whether carrying is limited by slots (dungeon/inventory.py).
    carry_limit: Literal['slots', 'off'] | None = None
    # Whether the world keeps moving in real time while the app is closed (dungeon/story_clock.py).
    clock: Literal['world', 'story', 'real_time'] | None = None
    # Whether the narrator gets the rule text that fits the turn (dungeon/rules/passages.py).
    rule_text: Literal['on', 'off'] | None = None
    # Who can stop the character leaving a scene (dungeon/leaving.py).
    leaving: Literal['anyone', 'fights', 'nobody'] | None = None
    # How much local politics goes on (dungeon/politics.py).
    politics: Literal['off', 'quiet', 'true_to_life', 'lively'] | None = None


class IronswornBuild(Input):
    """An Ironsworn character (dungeon/rules/ironsworn.py build): 3, 2, 2, 1, 1 on the five stats, three assets."""
    stats: dict[str, int]
    assets: list[str] = Field(default_factory=list, max_length=6)


class BrpBuild(Input):
    """A BRP character (dungeon/rules/brp.py build): bought characteristics, a profession and a personality."""
    characteristics: dict[str, int]
    profession: str = Field(min_length=1, max_length=80)
    personality: str = Field(min_length=1, max_length=80)


class NarrativeBuild(Input):
    """A Narrative Only character (dungeon/rules/narrative.py build): what they are good and bad at, both optional."""
    good_at: list[str] = Field(default_factory=list, max_length=6)
    bad_at: list[str] = Field(default_factory=list, max_length=6)


class FateBuild(Input):
    """A Fate character (dungeon/rules/fate.py build): aspects, the approaches' array placed, stunts."""
    high_concept: str = Field(min_length=1, max_length=120)
    trouble: str = Field(default='', max_length=120)
    aspects: list[str] = Field(default_factory=list, max_length=3)
    approaches: dict[str, int]
    stunts: list[str] = Field(default_factory=list, max_length=3)


class StoryStart(Input):
    """A premade character by id, or one the player made: who they are and their bought stats."""
    premade_id: str | None = Field(None, min_length=1, max_length=80)
    persona: PersonaInput | None = None
    stats: dict[str, int] | None = None
    # The arc (how far the character can rise) and its pace (dungeon/tiers.py); the world's own when left out.
    arc: Literal['grounded', 'classic', 'epic'] | None = None
    pace: Literal['slow', 'steady', 'fast'] | None = None
    # How hard the director's hand pushes (dungeon/director.py).
    hand: Literal['soft', 'guiding', 'firm'] | None = None
    # Ironman (dungeon/chapters.py): no going back for the whole campaign, so death is final.
    ironman: bool = False
    legacy: LegacyChoice | None = None
    # The ruleset (dungeon/sheet.py), locked for the campaign; the world's own when left out.
    ruleset: Literal['marvel', 'srd52', 'ironsworn', 'brp', 'narrative', 'fate'] | None = None
    build: Srd52Build | None = None
    ironsworn: IronswornBuild | None = None
    # Session zero (dungeon/table.py): the campaign's rules from a preset, fine-tuned.
    table: TableUpdate | None = None
    brp: BrpBuild | None = None
    narrative: NarrativeBuild | None = None
    fate: FateBuild | None = None


@router.get('/start')
def start_choices(request: Request):
    return campaign.view(request.app.state.database)


@router.post('/start')
def start(request: Request, body: StoryStart):
    return campaign.begin(request.app.state.database, body.premade_id, body.persona, body.stats, body.arc,
                          body.pace, body.hand, body.ironman, body.legacy and body.legacy.model_dump(), body.ruleset,
                          body.build and body.build.model_dump(), body.ironsworn and body.ironsworn.model_dump(),
                          body.table and body.table.model_dump(exclude_none=True), body.brp and body.brp.model_dump(),
                          body.narrative and body.narrative.model_dump(), body.fate and body.fate.model_dump())


class StoryBack(Input):
    message_id: str = Field(min_length=1, max_length=80)


@router.post('/back')
def back(request: Request, body: StoryBack):
    """Back to before one of the player's lines, as a new branch; the story so far is kept."""
    return story.back(request.app.state.database, body.message_id)


@router.post('/branches/{branch_id}/switch')
def switch_branch(request: Request, branch_id: str):
    return story.switch_branch(request.app.state.database, branch_id)


class ChapterClose(Input):
    title: str = Field('', max_length=80)


@router.post('/chapters/close')
def close_chapter(request: Request, body: ChapterClose):
    """The player ends the chapter here, naming it if they like; their next line opens the next one."""
    database = request.app.state.database
    with database.connect(write=True) as connection:
        chapters.mark(connection, 'player', body.title)
    return story.story(database)


@router.get('/chapters/{chapter_id}')
def read_chapter(request: Request, chapter_id: str, branch_id: str | None = None):
    """A chapter's lines as they were told in a branch (the one being played by default), to read."""
    with request.app.state.database.connect() as connection:
        return {'lines': chapters.read(connection, chapter_id, branch_id)}


@router.post('/chapters/{chapter_id}/back')
def chapter_back(request: Request, chapter_id: str):
    """Play on from the start of a chapter in the tree, with new dice."""
    return story.chapter_back(request.app.state.database, chapter_id)


class BookmarkInput(Input):
    message_id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=80)


@router.post('/bookmarks')
def add_bookmark(request: Request, body: BookmarkInput):
    database = request.app.state.database
    with database.connect(write=True) as connection:
        chapters.bookmark(connection, body.message_id, body.name, database.now())
    return story.story(database)


@router.delete('/bookmarks/{bookmark_id}')
def remove_bookmark(request: Request, bookmark_id: str):
    database = request.app.state.database
    with database.connect(write=True) as connection:
        chapters.unbookmark(connection, bookmark_id)
    return story.story(database)


@router.post('/bookmarks/{bookmark_id}/go')
def go_to_bookmark(request: Request, bookmark_id: str):
    return story.bookmark_go(request.app.state.database, bookmark_id)


@router.get('/table')
def read_table(request: Request):
    with request.app.state.database.connect() as connection:
        return table.rules(connection)


@router.put('/table')
def change_table(request: Request, body: TableUpdate):
    database = request.app.state.database
    with database.connect(write=True) as connection:
        table.choose(connection, body.model_dump(exclude_none=True), database.now())
        return table.rules(connection)


class NotebookNote(Input):
    text: str = Field(min_length=1, max_length=4000)


@router.get('/dice-log')
def dice(request: Request):
    """Every roll of the branch, turn by turn, with how long each turn took (dungeon/dice_log.py); only while the
    dice are shown."""
    with request.app.state.database.connect() as connection:
        return dice_log.log(connection, story.dice_shown(connection))


@router.get('/notebook')
def notebook(request: Request):
    """The player's own notes, across every branch; no model reads them (dungeon/chapters.py)."""
    with request.app.state.database.connect() as connection:
        return {'notes': chapters.notebook(connection)}


@router.post('/notebook')
def add_to_notebook(request: Request, body: NotebookNote):
    database = request.app.state.database
    with database.connect(write=True) as connection:
        chapters.write_note(connection, body.text, database.now())
        return {'notes': chapters.notebook(connection)}


@router.patch('/notebook/{note_id}')
def change_notebook(request: Request, note_id: str, body: NotebookNote):
    database = request.app.state.database
    with database.connect(write=True) as connection:
        chapters.write_note(connection, body.text, database.now(), note_id)
        return {'notes': chapters.notebook(connection)}


@router.delete('/notebook/{note_id}')
def remove_from_notebook(request: Request, note_id: str):
    database = request.app.state.database
    with database.connect(write=True) as connection:
        chapters.remove_note(connection, note_id)
        return {'notes': chapters.notebook(connection)}


class ArtAsk(Input):
    kind: Literal['portrait', 'place', 'scene', 'passage']
    subject: str = Field(default='', max_length=200)


class Enrolment(Input):
    classes: list[str] | None = Field(default=None, max_length=20)


class JournalNote(Input):
    subject: str = Field(min_length=1, max_length=120)
    text: str = Field(min_length=1, max_length=500)


class Trade(Input):
    qty: int = Field(1, ge=1, le=99)


class Purchase(Trade):
    item_id: str = Field(min_length=1, max_length=80)


class Sale(Trade):
    inventory_id: str = Field(min_length=1, max_length=80)


class JournalChange(Input):
    text: str = Field(min_length=1, max_length=500)


def journal_view(connection, database) -> dict:
    behind = record.gm_view(connection)
    return {'entries': record.entries(connection, known_only=not behind), 'gm': behind,
            'summary': record.summary(connection)['text'],
            'quests': quests.view(connection, story_clock.now(connection, database.clock)),
            'institutions': institutions.view(connection, story_clock.now(connection, database.clock)),
            'threads': director.journal(connection)}


@router.get('/journal')
def journal(request: Request):
    """What the player's character knows, from the record (dungeon/record.py); hidden truth stays out."""
    with request.app.state.database.connect() as connection:
        return journal_view(connection, request.app.state.database)


@router.post('/journal')
def add_note(request: Request, body: JournalNote):
    database = request.app.state.database
    with database.connect(write=True) as connection:
        record.add(connection, 'fact', body.subject, body.text, database.now(), 'player')
        return journal_view(connection, request.app.state.database)


@router.patch('/journal/{entry_id}')
def change_note(request: Request, entry_id: str, body: JournalChange):
    database = request.app.state.database
    with database.connect(write=True) as connection:
        record.correct(connection, entry_id, database.now(), body.text)
        return journal_view(connection, request.app.state.database)


@router.delete('/journal/{entry_id}')
def remove_note(request: Request, entry_id: str):
    database = request.app.state.database
    with database.connect(write=True) as connection:
        record.correct(connection, entry_id, database.now())
        return journal_view(connection, request.app.state.database)


@router.post('/journal/{entry_id}/regenerate')
async def regenerate_note(request: Request, entry_id: str):
    """The GM view asks the Continuity model again for one fact it pulled from the story (dungeon/record.py)."""
    await record.regenerate(request.app.state, entry_id)
    with request.app.state.database.connect() as connection:
        return journal_view(connection, request.app.state.database)


class Feelings(Input):
    trust: int | None = Field(None, ge=-5, le=5)
    affection: int | None = Field(None, ge=-5, le=5)
    respect: int | None = Field(None, ge=-5, le=5)
    fear: int | None = Field(None, ge=0, le=5)
    desire: int | None = Field(None, ge=0, le=5)


class Standing(Input):
    value: int = Field(ge=-5, le=5)


def gm_view(connection) -> dict:
    return gm.view(connection, tiers.world_of(story.scene_row(connection)['city_id']))


@router.get('/gm')
def behind_the_story(request: Request):
    """The GM view (dungeon/gm.py): everything the game keeps behind the story, secrets included."""
    with request.app.state.database.connect() as connection:
        return gm_view(connection)


@router.patch('/gm/people/{key}')
def set_feelings(request: Request, key: str, body: Feelings):
    with request.app.state.database.connect(write=True) as connection:
        gm.set_feelings(connection, key, body.model_dump(exclude_none=True))
        return gm_view(connection)


@router.put('/gm/factions/{faction_id}')
def set_standing(request: Request, faction_id: str, body: Standing):
    with request.app.state.database.connect(write=True) as connection:
        gm.set_standing(connection, faction_id, body.value)
        return gm_view(connection)


class BeatChange(Input):
    cut: bool | None = None
    position: int | None = Field(None, ge=0, le=20)


@router.post('/gm/seeds/{seed_id}/cash-in')
def cash_in_seed(request: Request, seed_id: str):
    """Ask for a seed to come back with the next GM note (dungeon/plotting.py)."""
    with request.app.state.database.connect(write=True) as connection:
        plotting.cash_in(connection, seed_id)
        return gm_view(connection)


@router.post('/gm/seeds/{seed_id}/retire')
def retire_seed(request: Request, seed_id: str):
    with request.app.state.database.connect(write=True) as connection:
        plotting.retire(connection, seed_id)
        return gm_view(connection)


@router.patch('/gm/beats/{beat_id}')
def change_beat(request: Request, beat_id: str, body: BeatChange):
    """Cut a planned beat, bring it back, or move it in its arc's order."""
    with request.app.state.database.connect(write=True) as connection:
        plotting.change_beat(connection, beat_id, body.cut, body.position)
        return gm_view(connection)


@router.delete('')
def clear(request: Request):
    return story.clear(request.app.state.database)


@router.get('/gear')
def gear(request: Request):
    """The character's purse and pack, and the shop window where the story is (dungeon/inventory.py)."""
    return story.gear(request.app.state.database)


@router.post('/shop/buy')
def buy(request: Request, body: Purchase):
    return story.trade(request.app.state.database, 'buy', body.item_id, body.qty)


@router.post('/shop/sell')
def sell(request: Request, body: Sale):
    return story.trade(request.app.state.database, 'sell', body.inventory_id, body.qty)


# Export (dungeon/book.py, dungeon/legacy.py) ------------------------------------------------------

def attachment(content: bytes, media_type: str, name: str) -> Response:
    return Response(content, media_type=media_type, headers={'Content-Disposition': f'attachment; filename="{name}"'})


@router.get('/export/book')
def export_book(request: Request, format: Literal['md', 'epub', 'pdf'] = 'md'):  # noqa: A002 - the query's name
    """The branch being played as a book."""
    database = request.app.state.database
    with database.connect() as connection:
        content, media_type = book.export(connection, format, database.now(), database=database)
    return attachment(content, media_type, f'story-{database.now()[:10]}.{format}')


@router.get('/export/campaign')
def export_campaign(request: Request):
    """The whole campaign (every branch, save, the record and the settings) as one file, to keep or move."""
    content, name = legacy.campaign_file(request.app.state.database)
    return attachment(content, 'application/zip', name)


@router.put('/institutions/{institution_id}')
def enroll(request: Request, institution_id: str, body: Enrolment):
    """The character joins a school or guild of this world, in the classes named (dungeon/institutions.py)."""
    database = request.app.state.database
    with database.connect(write=True) as connection:
        world = tiers.world_of(story.scene_row(connection)['city_id'])
        joined = world and institutions.enroll(connection, world, institution_id, body.classes,
                                               story_clock.now(connection, database.clock))
        require(bool(joined), 'That institution is not in this world.', 404)
        return journal_view(connection, database)


@router.delete('/institutions/{institution_id}')
def leave(request: Request, institution_id: str):
    database = request.app.state.database
    with database.connect(write=True) as connection:
        institutions.leave(connection, institution_id)
        return journal_view(connection, database)


@router.get('/art')
def gallery(request: Request):
    """The pictures made in the story (dungeon/art.py), the newest of each subject, marked when out of date."""
    return {'art': art.gallery(request.app.state.database)}


@router.get('/theme')
def theme(request: Request):
    """The colors of the world the story is in, when its package ships some (dungeon/world_theme.py)."""
    return world_theme.current(request.app.state.database)


@router.get('/art/stage')
def art_stage(request: Request):
    """The place's picture behind the story and the portraits of who is here (dungeon/art.py stage)."""
    return art.stage(request.app.state.database)


@router.post('/art')
async def ask_art(request: Request, body: ArtAsk):
    """A picture asked for: a portrait (`subject` 'player' or someone met), the place, the scene, or a passage (its
    message id). It is made in the background; the gallery shows it when it is done."""
    made = art.request(request.app.state.database, body.kind, body.subject)
    if (running := art.start(request.app.state, made['id'])) is not None:
        await running
    return {'art': art.gallery(request.app.state.database), 'asked': made['id']}


@router.get('/art/backdrop/{world}/{name}')
def art_backdrop(world: str, name: str):
    """A world's stock picture of a kind of place (dungeon/art.py backdrop)."""
    return Response(art.backdrop_file(world, name), media_type='image/webp',
                    headers={'Cache-Control': 'max-age=86400'})


@router.get('/art/card/{world}/{name}')
def art_card(world: str, name: str):
    """The picture of one of a world's Life Cards, or its card back (dungeon/happenings.py card_art)."""
    return Response(happenings.card_file(world, name), media_type='image/webp',
                    headers={'Cache-Control': 'max-age=86400'})


@router.get('/art/keyart/{world}')
def art_keyart(world: str):
    """A world's key art, on the title screen (dungeon/world_select.py)."""
    return Response(world_select.keyart(world), media_type='image/webp', headers={'Cache-Control': 'max-age=86400'})


@router.get('/worlds')
def title_worlds(request: Request):
    """The worlds the title screen offers, the one the story is in marked (dungeon/world_select.py)."""
    return world_select.choices(request.app.state.database)


@router.post('/worlds/{world}/enter')
async def enter_world(request: Request, world: str):
    """Into the persona's world there, made first when they have none. Runs on the event loop, like a switch."""
    return world_select.enter(request.app.state, world)


@router.get('/art/portrait/{world}/{name}')
def art_portrait(world: str, name: str):
    """A world's stock portrait of a kind of person (dungeon/art.py stock_portrait)."""
    return Response(art.portrait_file(world, name), media_type='image/webp',
                    headers={'Cache-Control': 'max-age=86400'})


@router.get('/art/{kind}/{world}/{name}')
def art_icon(kind: Literal['emblem', 'icon'], world: str, name: str):
    """A world's emblem for a faction, or its icon for an item (dungeon/icons.py)."""
    return Response(icons.file(kind, world, name), media_type='image/webp', headers={'Cache-Control': 'max-age=86400'})


@router.get('/art/{art_id}/file')
def art_file(request: Request, art_id: str):
    return FileResponse(art.file_of(request.app.state.database, art_id))
