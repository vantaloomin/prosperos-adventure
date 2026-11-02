"""Serve the Dungeon with a clock the acceptance driver can move forward.

The host clock is never changed. `POST /acceptance/clock` with `{"hours": 20}` moves the app's
clock forward (negative hours move it back, to test clock rollback); `GET` reports it.

    DUNGEON_DATA_DIR=... DUNGEON_API_KEY=k python scripts/acceptance/serve.py --port 8785
"""
import argparse
from datetime import UTC, datetime, timedelta

import uvicorn
from fastapi import Request
from fastapi.routing import APIRoute

from dungeon.clock import Clock
from dungeon.main import create_app


class ShiftedClock(Clock):
    def __init__(self):
        self.offset = timedelta()

    def now(self) -> datetime:
        return datetime.now(UTC) + self.offset


def build():
    clock = ShiftedClock()
    app = create_app(clock=clock)

    async def move(request: Request):
        body = await request.json() if request.method == 'POST' else {}
        clock.offset += timedelta(hours=float(body.get('hours', 0)))
        return {'now': clock.now().isoformat(), 'offset_hours': clock.offset.total_seconds() / 3600}

    # Ahead of the interface's catch-all static mount.
    app.router.routes.insert(0, APIRoute('/acceptance/clock', move, methods=['GET', 'POST']))
    return app


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8785)
    arguments = parser.parse_args()
    uvicorn.run(build(), host='127.0.0.1', port=arguments.port, log_level='warning')


if __name__ == '__main__':
    main()
