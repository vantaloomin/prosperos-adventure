"""Priority admission for owned inference; cancellation never releases a lease.

Copied from prosperos-study server/providers/scheduling.py at bbcbde4. Changes: Dungeon work
kinds replace the Study's writing kinds. Admission is in-process and counts requests, not GPU memory.
"""
import asyncio
import time
from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Callable
from urllib.parse import urlsplit

from dungeon.errors import DomainError
from dungeon.providers.urls import is_loopback


@dataclass(frozen=True)
class Work:
    priority: int = 10
    kind: str = 'requested assistance'
    background: bool = False
    validate: Callable | None = None


CONVERSATION = Work(0, 'conversation')
LIFE_SYNTHESIS = Work(20, 'life synthesis', True)
MAINTENANCE = Work(30, 'memory maintenance', True)
CURRENT_WORK = ContextVar('provider_work', default=Work())
# A model server running one request at a time keeps only the last prompt it read. Background work right after a
# reply would replace the chat's prompt, so the next reply would start from scratch: it waits until the user pauses.
HOLD_AFTER_REPLY = 90


@contextmanager
def work_scope(work):
    token = CURRENT_WORK.set(work)
    try:
        yield
    finally:
        CURRENT_WORK.reset(token)


def resource_for(config):
    parts = urlsplit(config.get('base_url', ''))
    if config.get('resource_group'):
        return 'shared:' + config['resource_group'], 1
    if config.get('provider') in {'local', 'kobold'} or is_loopback(parts.hostname):
        return 'local-inference', 1
    if config.get('provider') == 'codex':
        return 'codex-cli', 1
    if config.get('provider') == 'claude_code':
        # Each Claude account has its own plan limits, so its own two places.
        return 'claude-cli' + (f":{config['cli_account_dir']}" if config.get('cli_account_dir') else ''), 2
    return f'{parts.scheme}://{parts.netloc.lower()}', 2


@dataclass(eq=False)
class Lease:
    resource: str
    work: Work
    sequence: int
    ready: asyncio.Future
    stop: asyncio.Event = field(default_factory=asyncio.Event)
    queued_at: float = field(default_factory=time.perf_counter)
    admitted_at: float | None = None


class RequestScheduler:
    def __init__(self):
        self.waiting = []
        self.active = []
        self.limits = {}
        self.sequence = 0
        self.foreground = 0
        self.quiet_until = 0.0
        self.held_until = {}
        self.blocked = {}
        self.wakeup = None

    @property
    def idle(self):
        return not self.foreground and not self.active and not self.waiting and time.monotonic() >= self.quiet_until

    @contextmanager
    def foreground_work(self):
        self.foreground += 1
        self.interrupt_background()
        try:
            yield
        finally:
            self.foreground -= 1
            self.dispatch()

    def composing(self, seconds=2):
        self.quiet_until = max(self.quiet_until, time.monotonic() + seconds)
        self.interrupt_background()
        self.dispatch()

    def interrupt_background(self, resource=None):
        for lease in self.active:
            if lease.work.background and (resource is None or lease.resource == resource):
                lease.stop.set()

    def block(self, resource, reason):
        self.blocked[resource] = reason
        self.dispatch()

    def dispatch(self):
        if self.wakeup:
            self.wakeup.cancel()
            self.wakeup = None
        for lease in sorted(self.waiting, key=lambda item: (item.work.priority, item.sequence)):
            self.admit(lease)
        delay = max([self.quiet_until, *self.held_until.values()]) - time.monotonic()
        if self.waiting and delay > 0:
            self.wakeup = asyncio.get_running_loop().call_later(delay, self.dispatch)

    def admit(self, lease):
        if lease.ready.cancelled():
            self.waiting.remove(lease)
            return
        if lease.resource in self.blocked:
            self.waiting.remove(lease)
            lease.ready.set_exception(DomainError(self.blocked[lease.resource], 409))
            return
        if lease.work.background and (self.foreground or time.monotonic() < max(
                self.quiet_until, self.held_until.get(lease.resource, 0.0))):
            return
        occupied = sum(item.resource == lease.resource for item in self.active)
        if occupied >= self.limits[lease.resource]:
            return
        self.waiting.remove(lease)
        self.active.append(lease)
        lease.admitted_at = time.perf_counter()
        lease.ready.set_result(None)

    @asynccontextmanager
    async def reserve(self, config, work=None, wait_seconds=None):
        """Admission to the model service; with `wait_seconds`, waiting longer than that fails visibly."""
        work = work or CURRENT_WORK.get()
        resource, limit = resource_for(config)
        self.limits[resource] = min(limit, self.limits.get(resource, limit))
        self.sequence += 1
        lease = Lease(resource, work, self.sequence, asyncio.get_running_loop().create_future())
        self.waiting.append(lease)
        if not work.background:
            self.interrupt_background(resource)
        self.dispatch()
        try:
            try:
                async with asyncio.timeout(wait_seconds):
                    await lease.ready
            except TimeoutError as error:
                raise DomainError('The model was still busy with other work when the time limit ran out. '
                                  'Try again in a moment.', 504, 'timeout') from error
            yield lease
        finally:
            if lease in self.waiting:
                self.waiting.remove(lease)
            if lease in self.active:
                self.active.remove(lease)
            if lease.work is CONVERSATION and self.limits[resource] == 1 and resource != 'codex-cli':
                self.held_until[resource] = time.monotonic() + HOLD_AFTER_REPLY
            self.dispatch()


class BackgroundInterrupted(DomainError):
    def __init__(self):
        super().__init__('Background work yielded to the conversation.', 409)
