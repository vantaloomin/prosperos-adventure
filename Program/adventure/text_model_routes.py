"""Settings > Models: profiles, the connection test and job assignments.

Routes adapted from prosperos-study server/profile_routes.py at bbcbde4.
"""
from fastapi import APIRouter, Request

from adventure import text_models
from adventure.database import decode
from adventure.providers import balance, cli_accounts
from adventure.providers.config import ConnectionProbe, MixUpdate, ProfileCreate, ProfileUpdate, RouteUpdate

router = APIRouter(prefix='/api/models')


def db(request: Request):
    return request.app.state.database


@router.get('')
def overview(request: Request):
    with db(request).connect() as connection:
        return text_models.overview(connection)


@router.post('/profiles', status_code=201)
def create_profile(body: ProfileCreate, request: Request):
    return text_models.create(db(request), request.app.state.vault, body)


@router.put('/profiles/{profile_id}')
def update_profile(profile_id: str, body: ProfileUpdate, request: Request):
    return text_models.update(db(request), request.app.state.vault, profile_id, body)


@router.post('/profiles/{profile_id}/duplicate', status_code=201)
def duplicate_profile(profile_id: str, request: Request):
    return text_models.duplicate(db(request), profile_id)


@router.delete('/profiles/{profile_id}')
async def delete_profile(profile_id: str, request: Request):
    result = text_models.delete(db(request), request.app.state.vault, profile_id)
    # The Built-in profile gone: its server stops and "Set it up for me" is offered again (adventure/ready.py).
    await request.app.state.ready.forget()
    return result


@router.post('/discover')
async def discover(body: ConnectionProbe, request: Request):
    """Test an unsaved form: list the service's models without generating anything."""
    key = text_models.probe_key(db(request), request.app.state.vault, body)
    return await request.app.state.provider.check(body.config.model_dump(), key)


@router.get('/cli-accounts')
async def cli_accounts_found():
    """The Claude Code and Codex accounts on this computer (claude, claude2, codex…), for a profile to pick."""
    return {'accounts': await cli_accounts.accounts_with_logins()}


@router.post('/profiles/{profile_id}/check')
async def check_profile(profile_id: str, request: Request):
    with db(request).connect() as connection:
        row = text_models.profile_row(connection, profile_id)
    config = {**decode(row['config']), 'credential_ref': row['credential_ref']}
    return await request.app.state.provider.check(config, text_models.key_for(request.app.state.vault,
                                                                                            config))


@router.get('/profiles/{profile_id}/usage')
async def profile_usage(profile_id: str, request: Request, fresh: bool = False):
    """Credits or usage the service reports for free, or null; never spends tokens."""
    with db(request).connect() as connection:
        row = text_models.profile_row(connection, profile_id)
    config = {**decode(row['config']), 'credential_ref': row['credential_ref']}
    if not balance.has_lookup(config):
        return None
    key = text_models.key_for(request.app.state.vault, config)
    return await request.app.state.provider.usage((row['id'], row['revision']), config, key, fresh)


@router.put('/routes')
def set_route(body: RouteUpdate, request: Request):
    return text_models.set_route(db(request), body.job, body.profile_id)


@router.put('/mix')
def set_mix(body: MixUpdate, request: Request):
    """The narrator's Mix: profiles that tell the story in turn or at random, each with its own settings."""
    return text_models.set_mix(db(request), body.job, body.profile_ids, body.mode, body.enabled)
