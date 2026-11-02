"""Launch buttons for local programs, and starting them all when the Dungeon starts (Settings > Models).

Each program runs on its own after it is started: closing the Dungeon leaves it running, as if the user
had opened it. Its output goes to logs/launch-<program>.log. Starting at boot is off until the user turns
it on, since it opens other programs; then they start one after another, each waiting for the one before
to answer, text models first.
"""
import asyncio
import errno
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx

from dungeon import local_programs
from dungeon.database import optional
from dungeon.errors import DomainError, require
from dungeon.local_programs import PROGRAMS

START_SECONDS = 300
STEP_SECONDS = 600
# Started programs get no console window, and keep running after the Dungeon closes.
DETACHED = ({'creationflags': getattr(subprocess, 'CREATE_NO_WINDOW', 0) | getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)}
            if sys.platform == 'win32' else {'start_new_session': True})
log = logging.getLogger('dungeon')
# What a saved ComfyUI path may be besides a ComfyUI folder: the desktop app or the user's own launch script.
COMFY_FILES = {'.exe', '.app'} | local_programs.WINDOWS_SCRIPTS | local_programs.SHELL_SCRIPTS
NOT_A_PROGRAM = {errno.ENOEXEC, 193}  # 193: Windows' "not a valid Win32 application".


def start_failure(label: str, error: OSError) -> str:
    """Why a program did not start, in plain words (Iris); the system's own words go beside it as `detail`."""
    log.warning('%s could not be started: %s', label, error)
    if isinstance(error, PermissionError):
        return (f"{label} couldn't start because your computer didn't allow it to run. Check that you can open it "
                'yourself, then try again.')
    if isinstance(error, FileNotFoundError):
        return f"{label} couldn't start: nothing is at that location any more. It may have moved or been uninstalled."
    if error.errno in NOT_A_PROGRAM or getattr(error, 'winerror', None) in NOT_A_PROGRAM:
        return f"{label} couldn't start: that file isn't a program. Choose the {label} program itself."
    return f"{label} couldn't start. The details are in the log (Settings > Developer)."


def comfy_install(path: Path) -> bool:
    return local_programs.is_comfy_folder(path) or (path.suffix.lower() in COMFY_FILES and path.exists())


def saved(connection, program: str) -> dict:
    return optional(connection, 'SELECT * FROM local_programs WHERE program=?', (program,)) or {
        'program': program, 'path': '', 'chosen': 0, 'model_path': ''}


def store(connection, program: str, timestamp: str, **values):
    row = {**saved(connection, program), **values}
    connection.execute('INSERT INTO local_programs (program, path, chosen, model_path, updated_at) VALUES (?, ?, ?, ?, ?) '
                       'ON CONFLICT(program) DO UPDATE SET path=excluded.path, chosen=excluded.chosen, '
                       'model_path=excluded.model_path, updated_at=excluded.updated_at',
                       (program, row['path'], row['chosen'], row['model_path'], timestamp))


def log_tail(path: Path, lines=4) -> str:
    try:
        text = path.read_text('utf-8', errors='replace').strip().splitlines()
    except OSError:
        return ''
    return ' '.join(text[-lines:])[-400:]


class Launcher:
    def __init__(self, database, spawn=None, run=None, transport: httpx.AsyncBaseTransport | None = None, finders=None):
        self.database = database
        self.spawn = spawn or subprocess.Popen
        self.run = run or subprocess.run
        self.transport = transport
        self.finders = finders or local_programs.FINDERS
        self.states: dict[str, dict] = {}
        self.tasks: dict[str, asyncio.Task] = {}
        self.folder = database.path.parent / 'logs'

    # --- What is in use, and where it is installed

    def install(self, program: str) -> tuple[Path | None, dict]:
        """The saved path, else one found now (and saved, so the search runs once)."""
        with self.database.connect() as connection:
            row = saved(connection, program)
        if row['path'] and (row['chosen'] or Path(row['path']).exists()):
            return Path(row['path']), row
        found = self.finders[program]()
        if found:
            with self.database.connect(write=True) as connection:
                store(connection, program, self.database.now(), path=str(found), chosen=0)
            row = {**row, 'path': str(found), 'chosen': 0}
        return found, row

    def model_file(self, row: dict, program_uses: list[dict]) -> str:
        """KoboldCpp needs the model file itself: the one saved, else the file named like the profile's model."""
        if row['model_path']:
            return row['model_path']
        found = local_programs.gguf_named(program_uses[0]['model'])
        if found:
            with self.database.connect(write=True) as connection:
                store(connection, 'kobold', self.database.now(), model_path=str(found))
        return str(found or '')

    @staticmethod
    def address(program_uses: list[dict]) -> str:
        return f"http://127.0.0.1:{program_uses[0]['port']}"

    async def answers(self, program: str, program_uses: list[dict]) -> bool:
        address = self.address(program_uses)
        try:
            async with httpx.AsyncClient(transport=self.transport, timeout=2, trust_env=False) as client:
                response = await client.get(address + PROGRAMS[program]['health'])
            return response.status_code < 500
        except httpx.HTTPError:
            return False

    async def view(self, program: str, program_uses: list[dict]) -> dict:
        install, row = await asyncio.to_thread(self.install, program)
        running = await self.answers(program, program_uses)
        state = self.states.get(program, {'state': 'idle', 'message': ''})
        if running and state['state'] != 'starting':
            state = {'state': 'running', 'message': ''}
        model = await asyncio.to_thread(self.model_file, row, program_uses) if program == 'kobold' else ''
        return {'program': program, 'label': PROGRAMS[program]['label'], 'address': self.address(program_uses),
                'used_by': [{'kind': use['kind'], 'id': use['id'], 'name': use['name']} for use in program_uses],
                'path': str(install or ''), 'path_chosen': bool(row['chosen']), 'model_path': model,
                'needs_model': program == 'kobold' and not model, **state}

    async def listing(self) -> dict:
        with self.database.connect() as connection:
            in_use = local_programs.uses(connection)
            auto = bool(optional(connection, 'SELECT auto_launch FROM workspace_settings WHERE id=1')['auto_launch'])
        # The computer's kind, so the path boxes show an example path of the right shape.
        system = 'windows' if local_programs.WINDOWS else 'mac' if sys.platform == 'darwin' else 'linux'
        return {'auto_launch': auto, 'system': system,
                'programs': [await self.view(program, found) for program, found in in_use.items()]}

    # --- Settings

    def choose(self, program: str, path: str | None, model_path: str | None):
        require(program in PROGRAMS, 'That program is not one the Dungeon can start.', 404)
        values = {}
        # A path typed as ~/... (as the examples on a Mac show) means the user's own folder.
        path, model_path = (str(Path(value).expanduser()) if value else value for value in (path, model_path))
        if path is not None:
            require(not path or Path(path).exists(), 'Nothing was found at that path.', 422)
            require(not path or program != 'comfyui' or comfy_install(Path(path)),
                    "That folder doesn't look like ComfyUI: there's no main.py in it. Choose the ComfyUI folder, "
                    'the ComfyUI app, or the script you start it with.', 422)
            values.update(path=path, chosen=1 if path else 0)
        if model_path is not None:
            require(not model_path or Path(model_path).is_file(), 'That model file was not found.', 422)
            values['model_path'] = model_path
        with self.database.connect(write=True) as connection:
            store(connection, program, self.database.now(), **values)

    def set_auto(self, enabled: bool):
        with self.database.connect(write=True) as connection:
            connection.execute('UPDATE workspace_settings SET auto_launch=?, updated_at=? WHERE id=1',
                               (int(enabled), self.database.now()))

    # --- Starting

    def program_uses(self, program: str) -> list[dict]:
        with self.database.connect() as connection:
            found = local_programs.uses(connection).get(program)
        require(found is not None, 'No profile or image backend on this computer uses that program.', 404)
        return found

    def launch(self, program: str) -> asyncio.Task:
        """Starts the program in the background, once; the view shows its progress."""
        task = self.tasks.get(program)
        if task is None or task.done():
            program_uses = self.program_uses(program)
            self.states[program] = {'state': 'starting', 'message': ''}
            task = self.tasks[program] = asyncio.create_task(self.start(program, program_uses))
        return task

    async def start(self, program: str, program_uses: list[dict]):
        try:
            if not await self.answers(program, program_uses):
                await self.begin(program, program_uses)
            self.states[program] = {'state': 'running', 'message': ''}
        except DomainError as error:
            self.states[program] = {'state': 'failed', 'message': error.message}
        except OSError as error:
            self.states[program] = {'state': 'failed', 'message': start_failure(PROGRAMS[program]['label'], error),
                                    'detail': error.strerror or str(error)}

    async def begin(self, program: str, program_uses: list[dict]):
        label = PROGRAMS[program]['label']
        install, row = await asyncio.to_thread(self.install, program)
        require(install is not None, f'{label} was not found on this PC. Type where it is installed.', 409)
        output = self.folder / f'launch-{program}.log'
        self.folder.mkdir(parents=True, exist_ok=True)
        if program == 'lmstudio':
            await asyncio.to_thread(self.steps, local_programs.lmstudio_steps(install, program_uses), output, label)
            return
        if program == 'kobold':
            model = await asyncio.to_thread(self.model_file, row, program_uses)
            require(bool(model), 'Choose the model file for KoboldCpp to load.', 409)
            command = local_programs.kobold_command(install, model, program_uses[0])
        elif program == 'ollama':
            command = [str(install), 'serve']
        else:
            command = local_programs.comfy_command(install, program_uses[0]['port'])
        process = self.open(command, output, program, program_uses, install)
        await self.until_ready(program, program_uses, process, output)

    def open(self, command: list[str], output: Path, program: str, program_uses: list[dict], install: Path):
        environment = {**os.environ, 'OLLAMA_HOST': f"127.0.0.1:{program_uses[0]['port']}"} if program == 'ollama' else None
        folder = install if install.is_dir() else install.parent
        with output.open('wb') as stream:
            return self.spawn(command, stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT,
                              cwd=str(folder), env=environment, **DETACHED)

    def steps(self, commands: list[list[str]], output: Path, label: str):
        with output.open('wb') as stream:
            for command in commands:
                done = self.run(command, stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT,
                                timeout=STEP_SECONDS, **DETACHED)
                if done.returncode != 0:
                    raise DomainError(f'{label} did not start: {log_tail(output)}', 503)

    async def until_ready(self, program: str, program_uses: list[dict], process, output: Path):
        deadline = time.monotonic() + START_SECONDS
        label = PROGRAMS[program]['label']
        while time.monotonic() < deadline:
            if await self.answers(program, program_uses):
                return
            # A launcher that hands over to another process (the ComfyUI desktop app) exits cleanly.
            if process.poll() not in (None, 0):
                raise DomainError(f'{label} stopped while starting. {log_tail(output)}', 503)
            await asyncio.sleep(2)
        raise DomainError(f'{label} did not answer within {START_SECONDS // 60} minutes. {log_tail(output)}', 503)

    async def launch_all(self):
        """At startup, when turned on: every program in use, one after another."""
        with self.database.connect() as connection:
            if not optional(connection, 'SELECT auto_launch FROM workspace_settings WHERE id=1')['auto_launch']:
                return
            in_use = list(local_programs.uses(connection))
        for program in in_use:
            await self.launch(program)
            state = self.states.get(program, {})
            if state.get('state') == 'failed':
                log.warning('%s did not start at launch: %s', PROGRAMS[program]['label'], state['message'])

