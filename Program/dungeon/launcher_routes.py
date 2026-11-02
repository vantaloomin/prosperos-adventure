"""Settings > Models > Local programs: launch buttons and starting them with the Dungeon (dungeon/launcher.py).
PC only (dungeon/phone/access.py): a phone never starts programs on the PC."""
from fastapi import APIRouter, Request
from pydantic import Field

from dungeon.models import Input

router = APIRouter(prefix='/api/models/launcher')


class LauncherSettings(Input):
    auto_launch: bool


class ProgramUpdate(Input):
    path: str | None = Field(default=None, max_length=1000)
    model_path: str | None = Field(default=None, max_length=1000)


def launcher(request: Request):
    return request.app.state.launcher


@router.get('')
async def show(request: Request):
    return await launcher(request).listing()


@router.put('')
async def change(body: LauncherSettings, request: Request):
    launcher(request).set_auto(body.auto_launch)
    return await launcher(request).listing()


@router.put('/{program}')
async def choose(program: str, body: ProgramUpdate, request: Request):
    launcher(request).choose(program, body.path and body.path.strip(), body.model_path and body.model_path.strip())
    return await launcher(request).listing()


@router.post('/{program}/launch')
async def launch(program: str, request: Request):
    launcher(request).launch(program)
    return await launcher(request).listing()
