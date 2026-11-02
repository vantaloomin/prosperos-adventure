"""Lorebook files (dungeon/lore.py): import them, and switch their books and entries on or off; and long texts for
the reference library (dungeon/library.py)."""
import base64
import binascii

from fastapi import APIRouter, Request

from dungeon import library, lore
from dungeon.errors import DomainError
from dungeon.models import LibraryFile, LoreFile, LoreSwitch, LoreTiming, LoreWhen

router = APIRouter(prefix='/api')


def db(request: Request):
    return request.app.state.database


@router.post('/import/lorebook')
def import_lorebook(request: Request, body: LoreFile):
    """A lorebook file (JSON or .lorebook), imported straight away."""
    return lore.bring(db(request), body.filename, body.data)


@router.get('/lore')
def list_lore(request: Request):
    return lore.listing(db(request))


@router.put('/lore/books/{book_id}')
def switch_book(request: Request, book_id: str, body: LoreSwitch):
    return lore.set_book(db(request), book_id, body.enabled)


@router.delete('/lore/books/{book_id}')
def delete_book(request: Request, book_id: str):
    return lore.remove_book(db(request), book_id)


@router.put('/lore/entries/{entry_id}')
def switch_entry(request: Request, entry_id: str, body: LoreSwitch):
    return lore.set_entry(db(request), entry_id, body.enabled)


@router.put('/lore/entries/{entry_id}/when')
def entry_when(request: Request, entry_id: str, body: LoreWhen):
    return lore.set_when(db(request), entry_id, body.when)


@router.put('/lore/entries/{entry_id}/timing')
def entry_timing(request: Request, entry_id: str, body: LoreTiming):
    return lore.set_timing(db(request), entry_id, body.model_dump(exclude_none=True))


@router.get('/library')
def list_library(request: Request):
    return library.listing(db(request))


@router.post('/library/books')
def add_book(request: Request, body: LibraryFile):
    try:
        source = base64.b64decode(body.data, validate=True)
    except (ValueError, binascii.Error) as error:
        raise DomainError('Choose the file again; it did not arrive whole.', 422) from error
    return library.add(db(request), body.filename, source)


@router.put('/library/books/{book_id}')
def switch_library_book(request: Request, book_id: str, body: LoreSwitch):
    return library.set_book(db(request), book_id, body.enabled)


@router.delete('/library/books/{book_id}')
def delete_library_book(request: Request, book_id: str):
    return library.remove_book(db(request), book_id)


@router.get('/library/books/{book_id}/passages')
def book_passages(request: Request, book_id: str, q: str = ''):
    return library.browse(db(request), book_id, q[:500])
