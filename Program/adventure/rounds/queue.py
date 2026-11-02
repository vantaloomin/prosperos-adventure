"""One writer at a time (docs/spec.md "Turn state and persistence": "One command queue").

Every input that can start, continue or change a turn (a line sent, Next in Watch, a reply to the reply card, a
retry, a re-ask, a second browser tab doing any of these) goes through `play`, which runs it under the open world's
own lock, one after another in the order they arrived. So two tabs can never start two turns at once.

- **Stale commands are dropped.** A command may say which turn it was issued against (`against`: the newest turn the
  client knew of, or None for none yet). If the story has moved on since, it is refused with 409 and code 'stale',
  and the client reloads instead of acting on a turn that is gone.
- **Settings wait for Idle.** Mode, cap and model changes are accepted at any time (adventure/rounds/seats.py
  `change` with `under_way`); they do not need the lock.
- **Cancel acts at once.** It does not queue behind the turn it cancels: the running work is cancelled, which
  discards its draft (adventure/rounds/engine.py `run`).
"""
import asyncio
from contextlib import asynccontextmanager

from adventure import timeline
from adventure.database import optional
from adventure.errors import DomainError
from adventure.rounds import turns

# `against` left out: the command does not depend on which turn is newest.
NOT_GIVEN = object()


class Rounds:
    """Each world's lock and the work running under it."""

    def __init__(self):
        self.locks: dict[str, asyncio.Lock] = {}
        self.running: dict[str, asyncio.Task] = {}

    def lock(self, world: str) -> asyncio.Lock:
        return self.locks.setdefault(world, asyncio.Lock())


def rounds_of(app) -> Rounds:
    if getattr(app, 'rounds', None) is None:
        app.rounds = Rounds()
    return app.rounds


def world_of(app) -> str:
    return str(app.database.path)


def head(connection) -> str | None:
    """The newest turn on the branch being played that is not thrown away: what a client's `against` must match."""
    where, values = timeline.visible(connection)
    row = optional(connection, f"SELECT t.id FROM round_turns t WHERE t.state != 'discarded' AND t.anchor_id IN "
                               f'(SELECT id FROM story_messages WHERE {where}) ORDER BY t.seq DESC, t.created_at DESC '
                               'LIMIT 1', values)
    return row['id'] if row else None


def stale() -> DomainError:
    return DomainError('The story moved on since this was sent. Reload to see where it is.', 409, 'stale')


def check(app, against: str | None | object):
    """Refuse a command issued against a turn that is no longer the newest; NOT_GIVEN skips the check."""
    if against is NOT_GIVEN:
        return
    with app.database.connect() as connection:
        if head(connection) != against:
            raise stale()


@asynccontextmanager
async def writing(app):
    """Hold the open world's lock for one command."""
    async with rounds_of(app).lock(world_of(app)):
        yield


async def play(app, work, against=NOT_GIVEN):
    """Run `work()` (a coroutine function) as the world's one writer, after the commands before it."""
    held = rounds_of(app)
    world = world_of(app)
    async with held.lock(world):
        check(app, against)
        task = asyncio.ensure_future(work())
        held.running[world] = task
        try:
            return await task
        except asyncio.CancelledError:
            if task.cancelled() and not asyncio.current_task().cancelling():
                raise DomainError('The turn was cancelled.', 409, 'cancelled') from None
            raise
        finally:
            held.running.pop(world, None)


def cancel(app, turn_id: str) -> bool:
    """Cancel the turn being played now, if it is `turn_id`: its draft is discarded. Acts without waiting its turn."""
    with app.database.connect() as connection:
        row = turns.under_way(connection)
    task = rounds_of(app).running.get(world_of(app))
    if row is None or row['id'] != turn_id or task is None:
        if row is not None and row['id'] == turn_id:
            # Open but nothing is running it (it waits on the reply card): thrown away here.
            with app.database.connect(write=True) as connection:
                turns.discard(connection, turn_id, 'cancelled')
            return True
        return False
    task.cancel()
    return True
