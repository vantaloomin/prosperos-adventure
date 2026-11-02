"""Author's note API (dungeon/authors_note.py): read and save the one note of a chat."""
from fastapi import APIRouter, Request
from pydantic import ConfigDict, Field

from dungeon import authors_note
from dungeon.models import Input

router = APIRouter(prefix='/api/authors-notes')


class AuthorsNote(Input):
    # Saved as typed, a space at the end included, so the box never changes under the cursor.
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=False)
    text: str = Field('', max_length=authors_note.LIMIT)
    enabled: bool = True


@router.get('/{chat}')
def read(request: Request, chat: str):
    with request.app.state.database.connect() as connection:
        authors_note.check_chat(connection, chat)
        return authors_note.read(connection, chat)


@router.put('/{chat}')
def save(request: Request, chat: str, body: AuthorsNote):
    database = request.app.state.database
    with database.connect(write=True) as connection:
        return authors_note.save(connection, chat, body.text, body.enabled, database.now())
