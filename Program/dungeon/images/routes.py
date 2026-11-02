"""Image backends API (PRD F3–F9): the image services the app can draw with, set up in Settings > Images.

Nothing draws yet: art arrives in Milestone 6. The backends, their checks and their model lists stay so they are
ready."""
import json
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import APIRouter, Request

from dungeon import hardware
from dungeon.database import decode, encode
from dungeon.errors import DomainError
from dungeon.images import backends, node_packs
from dungeon.images.adapters.base import AdapterError
from dungeon.images.adapters.comfyui import (
    FAMILIES,
    SAMPLER_LISTS,
    built_in,
    default_files,
    default_sampler,
    family_first,
    family_of,
)
from dungeon.images.adapters.hosted import api_base
from dungeon.images.models import BackendCreate, BackendFields, BackendMove, ModelProbe
from dungeon.providers.urls import is_loopback, validate_compatible_url

router = APIRouter(prefix='/api/images')
MODEL_LINKS = Path(__file__).parent / 'model_links.json'


def db(request: Request):
    return request.app.state.database


def adapters(request: Request) -> dict:
    return request.app.state.image_adapters


def fit(request: Request, backend_id: str, options=None) -> dict:
    """Puts a ComfyUI server on this computer on a model file its graphics card holds (hardware.fit_images), and
    returns the backend as it now is."""
    computer = request.app.state.hardware.computer()
    with db(request).connect(write=True) as connection:
        hardware.fit_images(connection, computer, options, only=backend_id)
        return backends.get(connection, backend_id)


def fitted_view(request: Request, backend_id: str) -> dict:
    backend = fit(request, backend_id)
    with db(request).connect() as connection:
        return backends.view(backend, connection)


@router.get('/backends')
def list_backends(request: Request):
    return {'backends': backends.listing(db(request))}


@router.post('/backends')
def create_backend(request: Request, body: BackendCreate):
    created = backends.create(db(request), request.app.state.vault, body)
    return fitted_view(request, created['id'])


@router.put('/backends/{backend_id}')
def update_backend(request: Request, backend_id: str, body: BackendFields):
    backends.update(db(request), request.app.state.vault, backend_id, body)
    return fitted_view(request, backend_id)


@router.get('/backends/{backend_id}/workflows')
def backend_workflows(request: Request, backend_id: str):
    """A ComfyUI backend's saved workflows, for editing. The listing says only whether each is set."""
    with db(request).connect() as connection:
        config = decode(backends.get(connection, backend_id)['config'])
    return {**{key: config.get(key) or '' for key in ('workflow', 'reference_workflow')},
            'built_in': json.dumps(built_in(config)),
            # Empty for a family with no built-in reference workflow (Anima, Booru models).
            'built_in_reference': json.dumps(reference) if (reference := built_in(config, reference=True)) else ''}


@router.post('/backends/{backend_id}/move')
def move_backend(request: Request, backend_id: str, body: BackendMove):
    return {'backends': backends.move(db(request), backend_id, body.position)}


@router.delete('/backends/{backend_id}')
def delete_backend(request: Request, backend_id: str):
    return {'backends': backends.delete(db(request), backend_id)}


@router.post('/backends/{backend_id}/check')
async def check_backend(request: Request, backend_id: str):
    backend = fit(request, backend_id)
    key = backends.backend_key(db(request), request.app.state.vault, backend)
    adapter = adapters(request)[backend['kind']]
    config = decode(backend['config'])
    card = hardware.best_card(request.app.state.hardware.computer())
    if config.get('unet_fit') and not config.get('unet_name') and card:
        config['fit_line'] = hardware.missing_fit_line(config['unet_fit'], card, family_of(config))
    return (await adapter.check(backend, config, key)).view()


@router.post('/backends/{backend_id}/install-nodes/{pack_id}')
async def install_nodes(request: Request, backend_id: str, pack_id: str):
    """Put a listed node pack into the custom_nodes folder of a ComfyUI server on this computer, at the
    user's press (node_packs). ComfyUI loads it when it next starts."""
    with db(request).connect() as connection:
        backend = backends.get(connection, backend_id)
    config = decode(backend['config'])
    if backend['kind'] != 'comfyui' or not is_loopback(urlsplit(config.get('base_url', '')).hostname):
        raise DomainError('Nodes can only be installed into a ComfyUI running on this computer.', 409)
    try:
        folders = await adapters(request)['comfyui'].folder_paths(config)
    except AdapterError as error:
        raise DomainError(error.message, 502) from error
    target = await node_packs.install(pack_id, folders)
    return {'installed': node_packs.PACKS[pack_id]['label'], 'folder': str(target)}


@router.post('/models')
async def list_models(request: Request, body: ModelProbe):
    """The image models a hosted provider lists, for the add form or a saved backend's connection, so the model
    can be picked rather than typed. Lists only: nothing is made. An unreachable list is not an error: the page
    then takes a typed name."""
    provider = backends.provider_for('hosted', body.provider)
    base_url = api_base(body.base_url) if provider == 'other' else backends.HOSTED_DEFAULTS[provider]['base_url']
    key = body.api_key or None
    if body.backend_id:
        with db(request).connect() as connection:
            backend = backends.get(connection, body.backend_id)
        saved = api_base(decode(backend['config']).get('base_url') or '')
        base_url = base_url or saved
        if not key and backend['provider'] == provider and base_url == saved:
            key = backends.backend_key(db(request), request.app.state.vault, backend)
    if not base_url:
        raise DomainError('Enter the API base URL.', 422)
    validate_compatible_url(base_url)
    if not key and not body.backend_id:
        # A new backend lists models with the key a text profile saved for the same service.
        unsaved = {'kind': 'hosted', 'provider': provider, 'credential_ref': None, 'config': encode({'base_url': base_url})}
        key = backends.backend_key(db(request), request.app.state.vault, unsaved)
    try:
        models = await adapters(request)['hosted'].models(provider, {'base_url': base_url}, key)
    except AdapterError as error:
        return {'ok': False, 'error': error.message, 'models': []}
    return {'ok': True, 'error': None, 'models': models}


@router.get('/backends/{backend_id}/files')
async def backend_files(request: Request, backend_id: str):
    """The model files and LoRAs a ComfyUI server offers the built-in workflow, from the address the
    user entered, the backend's model family's first (`matching` lists those). An unreachable server is not an
    error: the page then takes typed names."""
    with db(request).connect() as connection:
        backend = backends.get(connection, backend_id)
    if backend['kind'] != 'comfyui':
        raise DomainError('Only a ComfyUI server lists its model files.', 422)
    config = decode(backend['config'])
    family = family_of(config)
    keys = [*FAMILIES[family].files, 'lora', *SAMPLER_LISTS]
    result = {'ok': True, 'error': None, 'family': family, 'defaults': fitted_defaults(family, fit(request, backend_id)),
              'sampler_defaults': default_sampler(family), 'options': {key: [] for key in keys},
              'matching': {key: [] for key in keys}}
    try:
        found = await adapters(request)['comfyui'].files(config)
    except AdapterError as error:
        result.update(ok=False, error=error.message)
        return result
    for key in keys:
        result['options'][key], result['matching'][key] = family_first(key, found.get(key, []), family)
    # The default model is the one the app picked for this computer's card from the files the server has.
    result['defaults'] = fitted_defaults(family, fit(request, backend_id, found.get('unet_name', [])))
    return result


def fitted_defaults(family: str, backend: dict) -> dict:
    """The family's own files, with the model the app picked for this computer's card in place of its own."""
    picked = decode(backend['config']).get('unet_fit')
    return {**default_files(family), **({'unet_name': picked} if picked else {})}


@router.get('/model-links')
def model_links():
    """Pages where the built-in workflow's model files can be downloaded (checked by hand)."""
    return {'links': json.loads(MODEL_LINKS.read_text(encoding='utf-8'))}


@router.post('/backends/{backend_id}/unblock')
def unblock_backend(request: Request, backend_id: str):
    """The user says they signed in again (F8)."""
    return backends.unblock(db(request), backend_id)
