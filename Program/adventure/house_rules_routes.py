"""The house rules API (adventure/rounds/house_rules.py): the campaign's rulebook at the Table and its rulings; and each
round turn's report and the status line (adventure/rounds/report.py); corrections to a committed turn and struck
inventions (adventure/rounds/corrections.py); and the "shown so far" sheet updates drafted at a chapter's close
(adventure/rounds/shown.py)."""
from typing import Literal

from fastapi import APIRouter, Request
from pydantic import Field

from adventure import record, story
from adventure.errors import DomainError, require
from adventure.models import Input
from adventure.rounds import corrections, house_rules, report, shown

router = APIRouter(prefix='/api/story')

Entries = list[str] | None


class HouseRulesUpdate(Input):
    """Any part of the book; a list arrives whole, as the Table shows it."""
    thoughts: str | None = None
    pane_title: str | None = Field(None, max_length=60)
    pane_row: str | None = Field(None, max_length=60)
    dialogue: Entries = Field(None, max_length=house_rules.MOST['dialogue'])
    punctuation: Entries = Field(None, max_length=house_rules.MOST['punctuation'])
    words: Entries = Field(None, max_length=house_rules.MOST['words'])
    phrases: Entries = Field(None, max_length=house_rules.MOST['phrases'])
    names: Entries = Field(None, max_length=house_rules.MOST['names'])
    reviewer: Literal['on', 'off', 'preset'] | None = None


class Ruling(Input):
    text: str = Field(min_length=1, max_length=500)


@router.get('/house-rules')
def read(request: Request):
    with request.app.state.database.connect() as connection:
        return house_rules.view(connection)


@router.put('/house-rules')
def change(request: Request, body: HouseRulesUpdate):
    database = request.app.state.database
    with database.connect(write=True) as connection:
        house_rules.change(connection, body.model_dump(exclude_none=True), database.now())
        return house_rules.view(connection)


@router.post('/rulings')
def rule(request: Request, body: Ruling):
    database = request.app.state.database
    with database.connect(write=True) as connection:
        house_rules.rule(connection, body.text, database.now())
        return house_rules.view(connection)


@router.delete('/rulings/{ruling_id}')
def withdraw(request: Request, ruling_id: str):
    database = request.app.state.database
    with database.connect(write=True) as connection:
        house_rules.withdraw(connection, ruling_id, database.now())
        return house_rules.view(connection)


@router.get('/turns/{turn_id}/report')
def turn_report(request: Request, turn_id: str):
    """A committed turn's report as the mode shows it. The GM view's fuller one, which marks the turn, is read through
    the GM view (adventure/gm.py)."""
    with request.app.state.database.connect() as connection:
        return report.report(connection, turn_id)


@router.get('/status-line')
def status_line(request: Request):
    with request.app.state.database.connect() as connection:
        return report.status(connection)


class Correction(Input):
    changes: list[dict] = Field(min_length=1, max_length=40)
    why: str = Field('', max_length=corrections.MOST_WHY)


class Strike(Input):
    name: str = Field(min_length=1, max_length=120)


@router.get('/turns/{turn_id}/corrections')
def turn_corrections(request: Request, turn_id: str):
    with request.app.state.database.connect() as connection:
        corrections.committed_turn(connection, turn_id)
        return corrections.of_turn(connection, turn_id)


@router.post('/turns/{turn_id}/corrections')
def correct(request: Request, turn_id: str, body: Correction):
    """A correction is made from the GM view: it can reach what the user's character doesn't know."""
    database = request.app.state.database
    with database.connect(write=True) as connection:
        require(record.gm_view(connection), 'Open the GM view to correct a turn.', 403)
        return corrections.correct(connection, turn_id, body.changes, body.why, database.now())


@router.post('/turns/{turn_id}/inventions/strike')
async def strike(request: Request, turn_id: str, body: Strike):
    """Strike one of the Writer's inventions; the passage that used it is rewritten without it when it can be."""
    database = request.app.state.database
    with database.connect(write=True) as connection:
        struck = corrections.strike(connection, turn_id, body.name, database.now())
    rewritten = False
    if struck['message_id'] and struck['passage']:
        try:
            await story.rewritten(request.app.state, struck['message_id'], struck['passage'],
                                  f'Take out {body.name}: the user struck it from the story.')
            rewritten = True
        except DomainError as failure:
            struck |= {'not_rewritten': failure.message}
    return struck | {'rewritten': rewritten}


class ShownReview(Input):
    apply: bool
    items: list[dict] | None = Field(None, max_length=shown.MOST)


@router.get('/shown')
def shown_updates(request: Request):
    """The sheet updates on this branch: drafts waiting for review, and those applied or dismissed."""
    with request.app.state.database.connect() as connection:
        return {'updates': shown.visible(connection)}


@router.post('/shown/{update_id}')
def review_shown(request: Request, update_id: str, body: ShownReview):
    """A draft is reviewed in the GM view: applied as it stands or as edited, or dismissed."""
    database = request.app.state.database
    with database.connect(write=True) as connection:
        require(record.gm_view(connection), 'Open the GM view to review a sheet update.', 403)
        return shown.decide(connection, update_id, body.apply, database.now(), body.items)
