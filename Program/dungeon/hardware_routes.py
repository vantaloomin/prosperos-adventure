"""Settings > Models and the welcome screen: what this computer can run (dungeon/hardware.py)."""
from fastapi import APIRouter, Request

router = APIRouter(prefix='/api/hardware')


@router.get('')
def show(request: Request, fresh: bool = False):
    return request.app.state.hardware.report(request.app.state.database, fresh)
