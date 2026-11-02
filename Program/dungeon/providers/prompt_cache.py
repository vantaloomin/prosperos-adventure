"""Instant replies on local models: each companion's prompt start is kept on disk and put back before they reply.

A local model keeps the work it did reading a prompt (its KV cache) for one prompt at a time. The start of every
companion's prompt stays the same from one message to the next (the stable-to-volatile order in
dungeon/memory/context.py), but as soon as another companion, a group or a background job uses the model, that
work is gone and the next reply reads everything again: minutes for a long prompt on a CPU.

llama.cpp's server can save what a slot has read to a file and load it back (`/slots/0?action=save|restore`,
started with `--slot-save-path`). So before the model reads a different prompt start than the one it holds, the
one it holds is saved, and the one it is about to read is loaded if it was saved before. Nothing is saved while
the same companion keeps talking, so a steady chat costs nothing extra. Prompts are told apart by their first
section (the character, or a group's shared part) and the model, so a changed character simply starts afresh, and
a short prompt (a background job's rules) is not worth a file.

It turns itself on for a server that answers like llama.cpp's and accepts a save, and off for one that does not;
any failure here only means the model reads the prompt again, never that a reply fails. The files live in the
server's own `--slot-save-path` folder, one per companion, each overwritten in place.
"""
import asyncio
import hashlib
import logging
import time
from dataclasses import dataclass, field

import httpx

PROVIDERS = {'local', 'compatible'}
# A prompt start shorter than this reads fast enough not to be worth a file.
MIN_START = 2000
SLOT = 0
PROBE_SECONDS, SLOT_SECONDS = 3, 120
# A server that could not be reached (not started yet, or still loading its model) is asked again after this long.
REPROBE_SECONDS = 60


@dataclass
class Server:
    supported: bool | None = None
    unreachable_at: float | None = None
    loaded: str | None = None
    saved: set[str] = field(default_factory=set)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


def root(base_url: str) -> str:
    base = base_url.rstrip('/')
    return base[:-3] if base.endswith('/v1') else base


def start_of(system: str) -> str:
    return system.split('\n## ', 1)[0]


def cache_key(config: dict, system: str) -> str | None:
    """Which saved prompt start this request reads, or None when it is not worth keeping."""
    start = start_of(system)
    if len(start) < MIN_START:
        return None
    digest = hashlib.sha256(f"{config['base_url']}|{config.get('model')}|{start}".encode()).hexdigest()
    return f'prospero-{digest[:24]}.bin'


class PromptCache:
    def __init__(self):
        self.servers: dict[str, Server] = {}

    def server(self, config: dict) -> Server:
        return self.servers.setdefault(root(config['base_url']), Server())

    async def probe(self, client: httpx.AsyncClient, config: dict, server: Server) -> bool:
        """Only llama.cpp's server reports its slots under /props."""
        if server.unreachable_at is not None and time.monotonic() - server.unreachable_at >= REPROBE_SECONDS:
            server.supported = server.unreachable_at = None
        if server.supported is None:
            try:
                response = await client.get(root(config['base_url']) + '/props', timeout=PROBE_SECONDS)
                server.supported = response.status_code == 200 and 'total_slots' in response.json()
                if response.status_code == 503:  # llama-server answers 503 while it loads the model.
                    server.unreachable_at = time.monotonic()
            except httpx.TransportError:
                server.supported, server.unreachable_at = False, time.monotonic()
            except (httpx.HTTPError, ValueError):
                server.supported = False
        return server.supported

    async def slot(self, client: httpx.AsyncClient, config: dict, server: Server, action: str, name: str) -> bool:
        try:
            response = await client.post(f"{root(config['base_url'])}/slots/{SLOT}", params={'action': action},
                                         json={'filename': name}, timeout=SLOT_SECONDS)
        except httpx.HTTPError:
            return False
        if response.status_code == 501 or (response.status_code == 400 and action == 'save'):
            # Started without --slot-save-path: nothing can be kept on this server.
            server.supported = False
            logging.getLogger('dungeon').info('The local model server cannot save prompts (start llama-server '
                                                'with --slot-save-path to keep them); replies read them afresh.')
        return response.status_code == 200

    async def prepare(self, client: httpx.AsyncClient, config: dict, system: str) -> dict:
        """Before a request: save what the slot holds if this request reads something else, load what it reads if it
        was kept. Returns what to add to the request body."""
        if config.get('provider') not in PROVIDERS:
            return {}
        server, wanted = self.server(config), cache_key(config, system)
        if (wanted is None and server.loaded is None) or not await self.probe(client, config, server):
            return {}  # Nothing to keep and nothing held: no need to ask the server anything.
        async with server.lock:
            if server.loaded and server.loaded != wanted and await self.slot(client, config, server, 'save',
                                                                              server.loaded):
                server.saved.add(server.loaded)
            if wanted and wanted != server.loaded and wanted in server.saved and server.supported:
                await self.slot(client, config, server, 'restore', wanted)
            server.loaded = wanted if server.supported else None
        return {'id_slot': SLOT, 'cache_prompt': True} if wanted and server.supported else {}
