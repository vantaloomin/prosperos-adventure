"""The house rules API (adventure/rounds/house_rules.py): the campaign's rulebook at the Table, and its rulings."""
from fastapi import APIRouter, Request
from pydantic import Field

from adventure.models import Input
from adventure.rounds import house_rules

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
