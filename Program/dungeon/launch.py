"""One foreground server that opens the browser and safely reuses its own running copy.

Adapted from prosperos-study scripts/launch_interface.py at bbcbde4: Dungeon identity, port and
health check; the server factory is dungeon.main:create_app.
"""
import argparse
import json
import os
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

from dungeon.identity import APP_ID, APP_NAME, DEFAULT_PORT

ROOT = Path(__file__).resolve().parent.parent
HOST = '127.0.0.1'


def probe(url) -> str:
    """'ready' when a Dungeon answers at url, 'foreign' for anything else, 'waiting' when nothing does."""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(url + 'api/health', timeout=0.4) as response:
            body = json.loads(response.read(4096))
        return 'ready' if isinstance(body, dict) and body.get('app_id') == APP_ID else 'foreign'
    except (urllib.error.HTTPError, ValueError):
        return 'foreign'
    except (urllib.error.URLError, OSError):
        return 'waiting'


def open_interface(url):
    try:
        if webbrowser.open(url):
            return
    except OSError:
        pass
    print(f'Open {url} in your browser.', flush=True)


def reuse(url, no_browser, wait=10.0) -> int:
    """The port is taken: reuse it only if it is this app, and never stop another process."""
    deadline = time.monotonic() + wait
    while time.monotonic() < deadline:
        state = probe(url)
        if state == 'ready':
            print(f'{APP_NAME} is already running at {url} Reusing it; no second server was started.', flush=True)
            if not no_browser:
                open_interface(url)
            return 0
        if state == 'foreign':
            break
        time.sleep(0.1)
    print(f'Cannot start: {url} is used by another program. Nothing was stopped. Close it or choose another '
          'port with --port, then retry.', flush=True)
    return 1


def answers(port) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.5)
        return probe.connect_ex((HOST, port)) == 0


def reserve_port(port):
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if os.name == 'nt':
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        else:
            # Without SO_REUSEADDR, connections our own last run closed (TIME_WAIT) hold the port for a
            # minute after a stop, so relaunching right away would report it as taken. On macOS it also lets
            # 127.0.0.1 be bound beside another program's wildcard listener, so check nothing answers first.
            if port and answers(port):
                listener.close()
                return None
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((HOST, port))
        if os.name != 'nt':
            # Two bound sockets may share an address under SO_REUSEADDR until one listens; listening now keeps
            # the reservation exclusive (Windows has SO_EXCLUSIVEADDRUSE for that).
            listener.listen()
        return listener
    except OSError:
        listener.close()
        return None


def open_when_ready(server, stopped, url):
    while not stopped.wait(0.1):
        if server.started:
            open_interface(url)
            return


def prepare_workspace() -> bool:
    """Open the workspace before serving, so a refused or failed upgrade is explained plainly."""
    from dungeon.database import Database
    from dungeon.errors import DomainError
    try:
        Database()
        return True
    except DomainError as error:
        print(f'{APP_NAME} could not open its workspace. {error.message}', flush=True)
        return False


def report_restore(name: str, result) -> int:
    from dungeon.errors import DomainError
    if isinstance(result, DomainError):
        print(f'Nothing was restored from {name}. {result.message}', flush=True)
        return 1
    print(f'Restored {name}.', flush=True)
    if result['previous']:
        print(f"The workspace it replaced was moved to {result['previous']}; its settings and connections carry "
              'over.', flush=True)
    else:
        print('Saved keys were not restored; add them again in Settings.', flush=True)
    return 0


def restore_backup(archive: Path) -> int:
    """Replace the active world with a backup while nothing else can open it (the port is held)."""
    from dungeon import restore, worlds
    from dungeon.errors import DomainError
    from dungeon.identity import database_path
    try:
        result = restore.replace_workspace(archive, worlds.active_path(database_path()))
    except DomainError as error:
        result = error
    return report_restore(archive.name, result)


def move_chosen_data():
    """Moving data into the app folder, chosen in Settings, runs here before anything opens it."""
    from dungeon import data_folder
    from dungeon.identity import database_path
    told = data_folder.apply_pending(database_path().parent)
    if told:
        print(told, flush=True)


def restore_chosen_backup():
    """A restore chosen in Settings runs here, before the workspace is opened."""
    from dungeon import restore, worlds
    from dungeon.identity import database_path
    chosen = restore.apply_pending(worlds.active_path(database_path()))
    if chosen:
        report_restore(*chosen)


def serve(listener, url, port, no_browser) -> int:
    import uvicorn

    from dungeon import logs

    # No request log: a URL can carry a search query. See dungeon/logs.py.
    config = uvicorn.Config('dungeon.main:create_app', factory=True, host=HOST, port=port, access_log=False,
                            timeout_graceful_shutdown=10, log_config=logs.config())
    server = uvicorn.Server(config)
    stopped = threading.Event()
    if not no_browser:
        threading.Thread(target=open_when_ready, args=(server, stopped, url), daemon=True).start()
    print(f'{APP_NAME}: {url}\nKeep this window open while you use it. Press Ctrl+C to stop.', flush=True)
    try:
        server.run(sockets=[listener])
        return 0 if server.started else 1
    except KeyboardInterrupt:
        return 0
    finally:
        stopped.set()
        listener.close()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=DEFAULT_PORT)
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--restore', type=Path, metavar='BACKUP',
                        help='Replace the world you are in with a backup (the current one is set aside), then exit.')
    args = parser.parse_args(argv)
    if not 1024 <= args.port <= 65535:
        parser.error('Choose a port between 1024 and 65535.')
    archive = args.restore.resolve() if args.restore else None
    os.chdir(ROOT)
    url = f'http://{HOST}:{args.port}/'
    if archive:
        listener = reserve_port(args.port)
        if listener is None:
            print(f'Close {APP_NAME} before restoring a backup.', flush=True)
            return 1
        with listener:
            return restore_backup(archive)
    if not (ROOT / 'dist' / 'index.html').is_file():
        installer = {'win32': 'install.bat', 'darwin': 'install.command'}.get(sys.platform, 'npm run build')
        print(f'The interface is not built. Run {installer} first.', flush=True)
        return 1
    listener = reserve_port(args.port)
    if listener is None:
        return reuse(url, args.no_browser)
    with listener:
        move_chosen_data()
        restore_chosen_backup()
        if not prepare_workspace():
            return 1
        return serve(listener, url, args.port, args.no_browser)


if __name__ == '__main__':
    raise SystemExit(main())
