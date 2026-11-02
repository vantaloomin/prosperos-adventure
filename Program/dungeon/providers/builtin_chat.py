"""Built-in chat: a llama.cpp server the Dungeon starts on this PC for the chat model "Set it up for me" downloaded
(dungeon/ready.py).

It is built-in recall's server (builtin_recall.py) with a graphics-card build and a chat command: the whole model on
the card where it fits (llama.cpp fits what it can and runs the rest from memory), a context the size the profile
asks for, the model's own chat template and thinking off, since a companion's reply is a text message, not a puzzle.
With thinking off it samples the way the models' cards recommend for non-thinking replies (`SAMPLING`).
The build is Vulkan on Windows, which runs on NVIDIA, AMD and Intel cards alike and is a 33 MB download beside about
650 MB for the CUDA build and its runtime; Apple silicon's build uses Metal, and an Intel Mac's runs on the processor.
The server keeps one port between launches, so the chat profile's address stays true and Settings > Models can test
it like any local server.
"""
import json
import os
import socket
import threading
import time
from pathlib import Path

from dungeon.providers.builtin_recall import RUNTIME_TAG, RUNTIMES, BuiltinRecall, free_port, threads

# Platform -> (asset, bytes, sha256). Checked by hand against the release on 2026-10-12.
GPU_RUNTIMES = {
    'windows-x64': (f'llama-{RUNTIME_TAG}-bin-win-vulkan-x64.zip', 33377746,
                    'd01301582c711a69b9747b5984710d6ca99e57d95f680d3d33753cec570b4cb6'),
    'macos-arm64': RUNTIMES['macos-arm64'],
    'macos-x64': RUNTIMES['macos-x64'],
}
CONTEXT = 16384
# A card with room to spare after the model and that context gets this bigger one (dungeon/ready.py `context_for`).
ROOMY_CONTEXT = 32768
# Qwen's recommended sampling for instruct (non-thinking) replies, the same on all three models offered: the model cards
# of Qwen/Qwen3.5-4B and Qwen/Qwen3.5-9B ("Instruct (or non-thinking) mode for general tasks") and Qwen/Qwen3.8-27B
# ("Instruct (or non-thinking) mode"), read 2026-10-12. The server starts with them, so a profile left blank still uses
# them, and "Set it up for me" writes them into the profile so Settings > Models shows them.
SAMPLING = {'temperature': 0.7, 'top_p': 0.8, 'top_k': 20, 'min_p': 0.0, 'presence_penalty': 1.5,
            'repetition_penalty': 1.0}
FLAGS = {'temperature': '--temp', 'top_p': '--top-p', 'top_k': '--top-k', 'min_p': '--min-p',
         'presence_penalty': '--presence-penalty', 'repetition_penalty': '--repeat-penalty'}
RESOURCE_GROUP = 'builtin-chat'


def state_file(root: Path) -> Path:
    return root / 'chat' / 'setup.json'


def read_state(root: Path) -> dict:
    """What "Set it up for me" has done on this computer (one file, shared by every world)."""
    try:
        found = json.loads(state_file(root).read_text('utf-8'))
    except (OSError, ValueError):
        return {}
    return found if isinstance(found, dict) else {}


def write_state(root: Path, state: dict):
    target = state_file(root)
    target.parent.mkdir(parents=True, exist_ok=True)
    # One partial per writer, so two saves at once never write into each other's file.
    partial = target.with_name(f'{target.name}.{os.getpid()}.{threading.get_ident()}.partial')
    partial.write_text(json.dumps(state, indent=2), 'utf-8')
    replace_soon(partial, target)


# Windows refuses to replace a file while another thread has it open to read (the page polling /api/ready during a
# download), so a replace that is turned away waits a moment and tries again.
REPLACE_TRIES = 20
REPLACE_WAIT = 0.025


def replace_soon(partial: Path, target: Path):
    for attempt in range(REPLACE_TRIES):
        try:
            partial.replace(target)
            return
        except PermissionError:
            if attempt == REPLACE_TRIES - 1:
                partial.unlink(missing_ok=True)
                raise
            time.sleep(REPLACE_WAIT)


def port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind(('127.0.0.1', port))
        except OSError:
            return False
    return True


class BuiltinChat(BuiltinRecall):
    """Starts, watches and stops the built-in chat model's server."""
    build = '-gpu'
    label = 'built-in chat model'
    model_label = 'chat model'
    folder_name = 'chat'
    start_seconds = 300

    def assets(self) -> dict:
        return GPU_RUNTIMES

    def wanted(self) -> tuple[str, str] | None:
        state = read_state(self.database.root)
        server = self.server()
        if state.get('status') != 'ready' or not state.get('model_path') or not server:
            return None
        return server, state['model_path']

    def choose_port(self) -> int:
        """The port saved at setup, so the profile's address keeps working; a new one only when another program
        took it. Replies always ask the running server (dungeon/providers/chat.py `builtin_address`)."""
        state = read_state(self.database.root)
        port = state.get('port')
        if isinstance(port, int) and port_free(port):
            return port
        state['port'] = port = free_port()
        write_state(self.database.root, state)
        return port

    def command(self, server: str, model: str, port: int) -> list[str]:
        context = read_state(self.database.root).get('context') or CONTEXT  # Set up before contexts were sized: 16K.
        sampling = [part for key, value in SAMPLING.items() for part in (FLAGS[key], str(value))]
        return [server, '-m', model, '--host', '127.0.0.1', '--port', str(port), '-ngl', '999', '-c', str(context),
                '-t', str(max(threads(), 4)), '--jinja', '--reasoning-budget', '0', *sampling,
                '--alias', Path(model).stem, '--no-webui']
