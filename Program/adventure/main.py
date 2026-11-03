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

from adventure import (
    agent_routes,
    authors_note_routes,
    auto_backup,
    house_rules_routes,
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
from adventure.assistant_routes import router as assistant_router
from adventure.database import Database
from adventure.debug_routes import calls_router, mix_router
from adventure.debug_routes import router as debug_router
from adventure.errors import DomainError
from adventure.gm_routes import router as gm_router
from adventure.hardware import Hardware
from adventure.hardware_routes import router as hardware_router
from adventure.identity import APP_NAME, CLIENT_HEADER, VERSION, WORLD_HEADER
from adventure.images import routes as image_routes
from adventure.images.adapters import default_adapters
from adventure.imports import file_routes
from adventure.launcher import Launcher
from adventure.launcher_routes import router as launcher_router
from adventure.mode_routes import router as mode_router
from adventure.packages_routes import router as packages_router
from adventure.providers.builtin_chat import BuiltinChat
from adventure.providers.builtin_recall import BuiltinRecall
from adventure.providers.chat import ChatProvider
from adventure.providers.decisions import DecisionProvider
from adventure.providers.embeddings import EmbeddingProvider
from adventure.providers.scheduling import RequestScheduler
from adventure.providers.vault import SystemVault
from adventure.ready import Ready, uses_builtin
from adventure.ready_routes import router as ready_router
from adventure.recall_routes import router as recall_router
from adventure.round_routes import router as round_router
from adventure.rounds import play as rounds_play
from adventure.rounds import queue as rounds_queue
from adventure.rounds import steps as rounds_steps  # noqa: F401 - every step plugged into the round loop
from adventure.routes import router
from adventure.text_model_routes import router as model_router
from adventure.updates import router as updates_router
from adventure.world import routes as world_routes

# The built interface (`npm run build`), served beside the API as prosperos-study server/main.py does.
FRONTEND = Path(__file__).parent.parent / 'dist'


async def guard_writes(request: Request, call_next):
    if request.method in {'POST', 'PUT', 'PATCH', 'DELETE'} and request.headers.get(CLIENT_HEADER) != 'workspace':
        return JSONResponse({'detail': 'Use the local Adventure app to make changes.'}, status_code=403)
    return await call_next(request)


async def stay_in_world(request: Request, call_next):
    """A request, and everything it starts, reads and writes the world open when it arrived
    (adventure/database.py PINNED). A page opened in another world (another tab, when this one switched) is told
    so instead of changing this one; it reloads into the world now open, named so it can say where (src/api.ts)."""
    database = request.app.state.database
    opened = request.headers.get(WORLD_HEADER)
    if opened and database.world and opened != database.world:
        data = worlds.load(database.root)
        world = data and worlds.find(data['worlds'], database.world)
        return JSONResponse({'detail': 'You moved to another world on another screen. Opening it here too.',
                             'code': 'world_changed', 'world': world['name'] if world else None}, status_code=409)
    with database.pin():
        return await call_next(request)


async def domain_error(_request: Request, error: DomainError):
    return JSONResponse({'detail': error.message, 'code': error.code}, status_code=error.status)


async def unexpected_error(request: Request, error: Exception):
    """Anything else: the traceback goes to the log (adventure/logs.py) and the page gets a message it can show,
    rather than a bare "Internal Server Error": what failed, the likely reason when it can be told, and a
    one-line detail for a bug report (adventure/troubleshoot.py)."""
    logging.getLogger('adventure').error('%s %s failed', request.method, request.url.path)
    log = logs.file_path()
    return JSONResponse({'detail': troubleshoot.for_request(request.method, request.url.path, error, str(log)),
                         'code': 'server_error', 'log': str(log)}, status_code=500)


async def invalid_request(_request: Request, error: RequestValidationError):
    details = [{'loc': issue['loc'], 'msg': issue['msg'], 'type': issue['type']} for issue in error.errors()]
    return JSONResponse({'detail': details}, status_code=422)


@asynccontextmanager
async def lifespan(app):
    tasks = []
    # A turn the app stopped in the middle of is thrown away; a round turn is played again from its snapshot
    # (adventure/rounds/play.py recover), one waiting on the reply card keeps waiting.
    replaying = rounds_play.recover(app.state)
    if app.state.background and replaying:
        tasks.append(asyncio.create_task(rounds_queue.play(
            app.state, lambda: rounds_play.replay(app.state, replaying))))
    if app.state.background:
        # Built-in recall loads its model now, so the first turn does not wait for it; so does the built-in text
        # model while it narrates, and a confirmed download carries on.
        app.state.builtin_recall.kick()
        app.state.ready.recover()
        if uses_builtin(app.state.database):
            app.state.builtin_chat.kick()
        tasks.append(asyncio.create_task(auto_backup.run_forever(app.state)))
        # Local programs the user asked to start with Adventure (off until turned on).
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
    # Decision models for the Referee (adventure/providers/decisions.py), on the same built-in server when chosen.
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
                 debug_router, worlds_routes.router, calls_router, mix_router, packages_router,
                 agent_routes.router, round_router, house_rules_routes.router, gm_router, mode_router, updates_router,
                 assistant_router):
        app.include_router(item)
    if FRONTEND.exists():
        app.mount('/', StaticFiles(directory=FRONTEND, html=True), name='frontend')
    return app
