"""FastAPI application. Middleware and error handlers follow prosperos-study server/main.py at bbcbde4."""
import asyncio
import logging
from contextlib import asynccontextmanager
from functools import partial
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from dungeon import (
    authors_note_routes,
    auto_backup,
    local_zone,
    logs,
    model_calls,
    politics_routes,
    story_routes,
    text_models,
    troubleshoot,
    workspace,
    world_data,
    worlds,
    worlds_routes,
)
from dungeon.database import Database
from dungeon.debug_routes import calls_router, mix_router
from dungeon.debug_routes import router as debug_router
from dungeon.errors import DomainError
from dungeon.hardware import Hardware
from dungeon.hardware_routes import router as hardware_router
from dungeon.identity import APP_NAME, CLIENT_HEADER, VERSION, WORLD_HEADER
from dungeon.images import routes as image_routes
from dungeon.images.adapters import default_adapters
from dungeon.imports import file_routes
from dungeon.launcher import Launcher
from dungeon.launcher_routes import router as launcher_router
from dungeon.packages_routes import router as packages_router
from dungeon.providers.builtin_chat import BuiltinChat
from dungeon.providers.builtin_recall import BuiltinRecall
from dungeon.providers.chat import ChatProvider
from dungeon.providers.decisions import DecisionProvider
from dungeon.providers.embeddings import EmbeddingProvider
from dungeon.providers.scheduling import RequestScheduler
from dungeon.providers.vault import SystemVault
from dungeon.ready import Ready, uses_builtin
from dungeon.ready_routes import router as ready_router
from dungeon.recall_routes import router as recall_router
from dungeon.routes import router
from dungeon.text_model_routes import router as model_router
from dungeon.world import routes as world_routes

# The built interface (`npm run build`), served beside the API as prosperos-study server/main.py does.
FRONTEND = Path(__file__).parent.parent / 'dist'


async def guard_writes(request: Request, call_next):
    if request.method in {'POST', 'PUT', 'PATCH', 'DELETE'} and request.headers.get(CLIENT_HEADER) != 'workspace':
        return JSONResponse({'detail': 'Use the local Dungeon app to make changes.'}, status_code=403)
    return await call_next(request)


async def stay_in_world(request: Request, call_next):
    """A request, and everything it starts, reads and writes the world open when it arrived
    (dungeon/database.py PINNED). A page opened in another world (another tab, when this one switched) is told
    so instead of changing this one; it reloads into the world now open (src/api.ts)."""
    database = request.app.state.database
    opened = request.headers.get(WORLD_HEADER)
    if opened and database.world and opened != database.world:
        return JSONResponse({'detail': 'You moved to another world on another screen. Opening it here too.',
                             'code': 'world_changed'}, status_code=409)
    with database.pin():
        return await call_next(request)


async def domain_error(_request: Request, error: DomainError):
    return JSONResponse({'detail': error.message, 'code': error.code}, status_code=error.status)


async def unexpected_error(request: Request, error: Exception):
    """Anything else: the traceback goes to the log (dungeon/logs.py) and the page gets a message it can show,
    rather than a bare "Internal Server Error": what failed, the likely reason when it can be told, and a
    one-line detail for a bug report (dungeon/troubleshoot.py)."""
    logging.getLogger('dungeon').error('%s %s failed', request.method, request.url.path)
    log = logs.file_path()
    return JSONResponse({'detail': troubleshoot.for_request(request.method, request.url.path, error, str(log)),
                         'code': 'server_error', 'log': str(log)}, status_code=500)


async def invalid_request(_request: Request, error: RequestValidationError):
    details = [{'loc': issue['loc'], 'msg': issue['msg'], 'type': issue['type']} for issue in error.errors()]
    return JSONResponse({'detail': details}, status_code=422)


@asynccontextmanager
async def lifespan(app):
    tasks = []
    if app.state.background:
        # Built-in recall loads its model now, so the first turn does not wait for it; so does the built-in text
        # model while it narrates, and a confirmed download carries on.
        app.state.builtin_recall.kick()
        app.state.ready.recover()
        if uses_builtin(app.state.database):
            app.state.builtin_chat.kick()
        tasks.append(asyncio.create_task(auto_backup.run_forever(app.state)))
        # Local programs the user asked to start with the Dungeon (off until turned on).
        tasks.append(asyncio.create_task(app.state.launcher.launch_all()))
    yield
    app.state.builtin_recall.shutdown()
    app.state.builtin_chat.shutdown()
    for task in tasks:
        task.cancel()


def create_app(database_path: str | Path | None = None, *, clock=None, vault=None, provider=None,
               background=True, embedder=None, image_adapters=None, builtin_spawn=None, builtin_transport=None,
               hardware=None, launcher=None, decider=None) -> FastAPI:
    app = FastAPI(title=APP_NAME, version=VERSION, lifespan=lifespan)
    app.state.database = Database(database_path, clock)
    world_data.use(app.state.database.root)  # The world packages the game reads (built-in ones built now).
    worlds.start(app.state.database)  # The world the user was last in; the first run makes the first world.
    workspace.adopt_pc_timezone(app.state.database, local_zone.detect())
    app.state.vault = vault or SystemVault()
    # Every model call goes through here, written down in full while Record model calls is on.
    app.state.provider = model_calls.Recording(provider or ChatProvider(), app.state.database)
    app.state.scheduler = RequestScheduler()
    app.state.embedder = embedder or EmbeddingProvider()
    app.state.builtin_recall = BuiltinRecall(app.state.database, builtin_spawn, builtin_transport)
    app.state.embedder.builtin = app.state.builtin_recall
    app.state.launcher = launcher or Launcher(app.state.database)
    app.state.hardware = hardware or Hardware()
    app.state.builtin_chat = BuiltinChat(app.state.database, builtin_spawn, builtin_transport)
    app.state.provider.inner.builtin_chat = app.state.builtin_chat
    app.state.provider.inner.learned_effort = partial(text_models.learn_effort, app.state.database)
    # Decision models for the Referee (dungeon/providers/decisions.py), on the same built-in server when chosen.
    app.state.decider = decider or DecisionProvider()
    app.state.decider.builtin_chat = app.state.builtin_chat
    app.state.ready = Ready(app.state.database, app.state.builtin_chat,
                            lambda: app.state.hardware.report(app.state.database), builtin_transport)
    app.state.image_adapters = image_adapters or default_adapters()
    app.state.background = background
    app.middleware('http')(stay_in_world)
    app.middleware('http')(guard_writes)
    app.add_exception_handler(DomainError, domain_error)
    app.add_exception_handler(RequestValidationError, invalid_request)
    app.add_exception_handler(Exception, unexpected_error)
    for item in (router, model_router, launcher_router, recall_router, hardware_router, ready_router, world_routes.router,
                 image_routes.router, politics_routes.router, story_routes.router, authors_note_routes.router, file_routes.router,
                 debug_router, worlds_routes.router, calls_router, mix_router, packages_router):
        app.include_router(item)
    if FRONTEND.exists():
        app.mount('/', StaticFiles(directory=FRONTEND, html=True), name='frontend')
    return app
