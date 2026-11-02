"""Configured image backends (PRD F5–F9).

Three classes: a ComfyUI instance, the Codex/ChatGPT subscription CLI and hosted image APIs.
Every backend is off until configured, and the user orders them. What a backend may receive
follows F6: a local ComfyUI instance takes NSFW requests; Codex, Google and the OpenAI API take
Safe requests only; any other image API takes Safe requests unless the user switches it to NSFW too
(Vanta, 2026-10-07: a provider like NovelAI accepts NSFW prompts under its own terms).
"""
from urllib.parse import urlsplit

from dungeon.database import decode, encode, identifier, many, one
from dungeon.errors import DomainError, require
from dungeon.images import content
from dungeon.images.adapters.comfyui import (
    DEFAULT_FAMILY,
    FAMILIES,
    SAMPLER_INPUTS,
    default_sampler,
    family_of,
    has_reference,
    tag_kind,
)
from dungeon.images.adapters.hosted import api_base
from dungeon.providers.urls import is_loopback, validate_compatible_url

HOSTED_DEFAULTS = {
    'openrouter': {'base_url': 'https://openrouter.ai/api/v1', 'api_style': 'chat', 'label': 'OpenRouter'},
    'google': {'base_url': 'https://generativelanguage.googleapis.com/v1beta/openai', 'api_style': 'images',
               'label': 'Google'},
    'openai': {'base_url': 'https://api.openai.com/v1', 'api_style': 'images', 'label': 'OpenAI API'},
    # NanoGPT's OpenAI-compatible route; its image models are listed at /images/models, not /models.
    'nanogpt': {'base_url': 'https://nano-gpt.com/api/v1', 'api_style': 'images', 'label': 'NanoGPT'},
    # NovelAI's own image API (adapters/novelai.py), with a persistent API token.
    'novelai': {'base_url': 'https://image.novelai.net', 'api_style': 'novelai', 'label': 'NovelAI'},
    'other': {'base_url': '', 'api_style': 'images', 'label': 'Image API'},
}
# Hosted providers the NSFW switch is offered for. Google and OpenAI's own API stay safe-only, like Codex.
NSFW_PROVIDERS = {'openrouter', 'nanogpt', 'novelai', 'other'}
KIND_LABELS = {'comfyui': 'ComfyUI', 'codex': 'Codex (ChatGPT subscription)'}
CONFIG_KEYS = ('base_url', 'model', 'workflow', 'reference_workflow', 'cli_path', 'api_style')
# ComfyUI only: the files chosen for the built-in workflow's loaders (see adapters/comfyui.py).
FILE_KEYS = ('unet_name', 'clip_name', 'clip_type', 'vae_name', 'ckpt_name', 'ref_unet_name')


def credential_ref(backend_id: str) -> str:
    return f'image-backend:{backend_id}'


# A text profile's service whose key an image API with no key of its own uses: the same provider, so the key a
# person saved once for chat also makes pictures. Google's image route sits under the same key as Gemini text.
TEXT_PROVIDERS = {'openai': 'openai', 'openrouter': 'openrouter', 'google': 'google', 'nanogpt': 'nanogpt',
                  'other': 'compatible'}


def text_profile_key(connection, backend: dict) -> dict | None:
    """The text model profile whose saved key this hosted backend borrows, or None. Only for a backend at its
    provider's usual address (or, for any other image API, a compatible text profile at the same address), so a key
    never reaches a server it was not entered for."""
    from dungeon.providers.config import DEFAULT_URLS

    if backend['kind'] != 'hosted' or backend['credential_ref'] or backend['provider'] not in TEXT_PROVIDERS:
        return None
    base_url = api_base(decode(backend['config']).get('base_url') or '')
    provider = TEXT_PROVIDERS[backend['provider']]
    if provider != 'compatible' and base_url != api_base(HOSTED_DEFAULTS[backend['provider']]['base_url']):
        return None
    wanted = base_url if provider == 'compatible' else DEFAULT_URLS[provider]
    for row in many(connection, 'SELECT name, config, credential_ref FROM model_profiles WHERE credential_ref IS NOT '
                    'NULL ORDER BY updated_at DESC, created_at DESC'):
        config = decode(row['config'])
        if config.get('provider') == provider and api_base(config.get('base_url') or '') == api_base(wanted):
            return row
    return None


def key_for(connection, vault, backend: dict) -> str | None:
    """The key a backend calls with: its own, else the one saved with a text profile for the same service."""
    if backend['credential_ref']:
        return vault.get(backend['credential_ref'])
    borrowed = text_profile_key(connection, backend)
    return vault.get(borrowed['credential_ref']) if borrowed else None


def backend_key(database, vault, backend: dict) -> str | None:
    if backend['credential_ref']:
        return vault.get(backend['credential_ref'])
    with database.connect() as connection:
        return key_for(connection, vault, backend)


def is_novelai(backend: dict) -> bool:
    """NovelAI's own image API, whose models read booru tags like the Booru family (adapters/novelai.py)."""
    return backend['kind'] == 'hosted' and backend['provider'] == 'novelai'


def is_local(backend: dict) -> bool:
    """F6: a ComfyUI instance on this computer is local; elsewhere only if the user marked it as a
    machine they control. Codex and hosted APIs are never local."""
    if backend['kind'] != 'comfyui':
        return False
    host = urlsplit(decode(backend['config']).get('base_url', '')).hostname
    return is_loopback(host) or bool(backend['controlled_machine'])


def can_allow_nsfw(kind, provider) -> bool:
    """Whether the user may switch this backend to take NSFW requests: image APIs other than Google
    and OpenAI. A local ComfyUI takes them anyway; Codex, Google and OpenAI never do."""
    return kind == 'hosted' and provider in NSFW_PROVIDERS


def accepts_nsfw(backend: dict) -> bool:
    return is_local(backend) or (can_allow_nsfw(backend['kind'], backend['provider'])
                                 and bool(backend.get('allows_nsfw')))


def takes_reference(backend: dict) -> bool:
    """Whether this backend can make a picture that follows an earlier one (the onboarding
    portraits): Codex attaches it to the prompt, chat-style APIs and OpenAI's image edits read it,
    and ComfyUI uses its family's built-in reference workflow (Krea 2, Qwen Image 2.1) or the user's own."""
    if backend['kind'] == 'codex':
        return True
    config = decode(backend['config'])
    if backend['kind'] == 'comfyui':
        return has_reference(config)
    from dungeon.images.adapters.hosted import takes_reference as hosted_takes
    return hosted_takes(config, backend['provider'])


def disclosure(backend: dict) -> str | None:
    """What a hosted request sends, shown before the provider is enabled (F9)."""
    if backend['kind'] == 'comfyui' and is_local(backend):
        return None
    if backend['kind'] == 'codex':
        destination = 'OpenAI, through the Codex CLI under your own codex login (your ChatGPT plan, or the API key ' \
            'Codex is signed in with)'
    elif backend['kind'] == 'comfyui':
        destination = 'the ComfyUI server at this address, which is not on this computer'
    else:
        destination = HOSTED_DEFAULTS[backend['provider']]['label'] if backend['provider'] != 'other' \
            else 'this image service'
    text = (f'Each image request sends its prompt (built from the event and the character\'s appearance '
            f'description) to {destination}. Their retention rules apply. Conversation and memories are '
            f'not sent.')
    if is_novelai(backend):
        text += ' NovelAI does not take reference pictures, so only the prompt is sent.'
    else:
        text += (' Reference pictures are sent only when you make profile pictures: the first one goes along with '
                 'the other two.')
    if backend['kind'] == 'codex':
        text += (' With Codex, each picture of your companion also sends their character sheet, and their first '
                 'picture takes two requests: one to draw the sheet (from their profile picture, if they have one), '
                 'then the picture.')
    if accepts_nsfw(backend) and not is_local(backend):
        text += (' NSFW requests go there too, so their terms decide what they will make and keep. '
                 'Prohibited requests are still never sent.')
    return text


def view(backend: dict, connection=None) -> dict:
    config = decode(backend['config'])
    borrowed = text_profile_key(connection, backend) if connection is not None else None
    return {'id': backend['id'], 'kind': backend['kind'], 'provider': backend['provider'], 'label': backend['label'],
            'enabled': bool(backend['enabled']), 'position': backend['position'],
            'base_url': config.get('base_url', ''), 'model': config.get('model', ''), 'style': config.get('style', ''),
            'api_style': config.get('api_style'), 'cli_path': config.get('cli_path', ''),
            'custom_workflow': bool(config.get('workflow')),
            'family': family_of(config) if backend['kind'] == 'comfyui' else None,
            # The model's own opening when the backend has none (the Booru family's quality tags), and whether
            # its prompts go out as booru tags (images/tags.py).
            'family_style': FAMILIES[family_of(config)].style if backend['kind'] == 'comfyui' else
            FAMILIES['booru'].style if is_novelai(backend) else None,
            'tag_prompts': backend['kind'] == 'comfyui' and tag_kind(config) is not None or is_novelai(backend),
            'model_files': {key: config.get(key, '') for key in FAMILIES[family_of(config)].files}
            if backend['kind'] == 'comfyui' else None,
            'model_fit': config.get('unet_fit') if backend['kind'] == 'comfyui' else None,
            'style_loras': config.get('style_loras', []) if backend['kind'] == 'comfyui' else None,
            'sampler': {key: config.get(key) for key in SAMPLER_INPUTS} if backend['kind'] == 'comfyui' else None,
            'reference_workflow': bool(config.get('reference_workflow')), 'takes_reference': takes_reference(backend),
            'has_key': backend['credential_ref'] is not None, 'key_from': borrowed['name'] if borrowed else None,
            'controlled_machine': bool(backend['controlled_machine']), 'concurrency': backend['concurrency'],
            'local': is_local(backend), 'accepts_nsfw': accepts_nsfw(backend),
            'allows_nsfw': bool(backend.get('allows_nsfw')),
            'nsfw_switch': can_allow_nsfw(backend['kind'], backend['provider']),
            'blocked_reason': backend['blocked_reason'], 'disclosure': disclosure(backend),
            'disclosure_accepted': backend['disclosure_accepted_at'] is not None,
            'experimental': backend['kind'] == 'codex'}


def ordered(connection, enabled_only=False) -> list[dict]:
    where = 'WHERE enabled=1 ' if enabled_only else ''
    return many(connection, f'SELECT * FROM image_backends {where}ORDER BY position, created_at')


def listing(database) -> list[dict]:
    with database.connect() as connection:
        return [view(backend, connection) for backend in ordered(connection)]


def get(connection, backend_id) -> dict:
    return one(connection, 'SELECT * FROM image_backends WHERE id=?', (backend_id,))


def validate(kind, provider, config, controlled_machine, allows_nsfw=False):
    if kind == 'comfyui':
        require(config.get('base_url'), 'Enter the address of your ComfyUI server.', 422)
        url = config['base_url']
        parts = urlsplit(url)
        require(parts.scheme in {'http', 'https'} and parts.hostname, 'Enter an http or https ComfyUI address.', 422)
        require(not any((parts.username, parts.password, parts.query, parts.fragment)),
                'Use a plain server address without credentials or query text.', 422)
        if config.get('workflow'):
            from dungeon.images.adapters.comfyui import parse_workflow
            parse_workflow(config['workflow'])
        if config.get('reference_workflow'):
            from dungeon.images.adapters.comfyui import parse_workflow
            parse_workflow(config['reference_workflow'], reference=True)
    elif kind == 'hosted':
        require(config.get('base_url'), 'Enter the API base URL.', 422)
        validate_compatible_url(config['base_url'])
        require(config.get('model'), 'Choose the image model to use.', 422)
    require(not (controlled_machine and kind != 'comfyui'),
            'Only a ComfyUI server can be marked as a machine you control.', 422)
    require(not allows_nsfw or can_allow_nsfw(kind, provider),
            'Only an image API other than Google or OpenAI can take NSFW requests; '
            'for NSFW images on this computer, use a local ComfyUI server.', 422)


def merged_config(kind, provider, previous: dict, body) -> dict:
    config = dict(previous)
    if not previous and kind == 'hosted':
        defaults = HOSTED_DEFAULTS[provider]
        config.update({'base_url': defaults['base_url'], 'api_style': defaults['api_style']})
    for key in CONFIG_KEYS:
        value = getattr(body, key)
        if value is not None:
            config[key] = api_base(value) if key == 'base_url' else value
    choose_family(config, kind, body)
    for key in FILE_KEYS:
        value = getattr(body, key)
        if value is not None:
            config[key] = value.strip()
        if kind != 'comfyui' or not config.get(key):
            config.pop(key, None)
    if body.style is not None:
        config['style'] = body.style.strip()
    if not config.get('style'):
        config.pop('style', None)
    comfy_settings(config, kind, body)
    if kind != 'hosted':
        config.pop('api_style', None)
    return config


def choose_family(config: dict, kind, body):
    """The model family whose built-in workflow a ComfyUI server runs (Krea 2 when unset). Files and
    sampler settings chosen for another family's workflow do not carry over, so a new family starts on
    its own."""
    if kind != 'comfyui' or body.family is None:
        return
    if body.family != family_of(config):
        for key in (*FILE_KEYS, *SAMPLER_INPUTS, 'unet_fit'):
            config.pop(key, None)
    config['family'] = body.family
    if body.family == DEFAULT_FAMILY:
        config.pop('family')


def comfy_settings(config: dict, kind, body):
    """The built-in workflow's sampler (a value equal to the workflow's own is stored as unset) and
    the style LoRAs, for ComfyUI only."""
    defaults = default_sampler(family_of(config))
    for key in SAMPLER_INPUTS:
        value = getattr(body, key)
        if value is not None:
            config[key] = value.strip() if isinstance(value, str) else value
        if kind != 'comfyui' or config.get(key) in (None, '') or config.get(key) == defaults[key]:
            config.pop(key, None)
    if body.style_loras is not None:
        config['style_loras'] = [{'name': lora.name.strip(), 'strength': lora.strength, 'trigger': lora.trigger.strip()}
                                 for lora in body.style_loras]
    if kind != 'comfyui' or not config.get('style_loras'):
        config.pop('style_loras', None)


def own_style(backend: dict) -> str | None:
    """The style this backend's prompts start with in place of the general one: the user's own for it,
    else its model family's (an anime model draws no photographs), else none."""
    config = decode(backend['config'])
    if config.get('style'):
        return config['style']
    if is_novelai(backend):
        return FAMILIES['booru'].style
    return FAMILIES[family_of(config)].style if backend['kind'] == 'comfyui' else None


def style_for(backend: dict | None, general: str | None) -> str | None:
    """The style that starts this backend's prompts: its own, or the general one when it has none."""
    own = own_style(backend) if backend else None
    return own or general


def require_safe_loras(backend: dict):
    """A style LoRA or a backend's own style never makes a server less strict: one whose words are not
    plainly safe needs a server that accepts NSFW requests (F6), so it is refused anywhere else."""
    if accepts_nsfw(backend):
        return
    style = decode(backend['config']).get('style')
    if style:
        found = content.classify({'prompt': style})
        require(found.tier == content.SAFE, f"This style reads as {', '.join(found.reasons) or 'not safe'}; "
                'it can only be used on a backend that takes NSFW requests.', 422)
    for lora in decode(backend['config']).get('style_loras') or []:
        found = content.classify({'prompt': f"{lora['name']}\n{lora['trigger']}"})
        require(found.tier == content.SAFE, f"The LoRA {lora['name']} reads as {', '.join(found.reasons) or 'not safe'}; "
                'it can only be used on a ComfyUI server on this computer or one you control.', 422)


def provider_for(kind, provider) -> str:
    if kind in {'comfyui', 'codex'}:
        return kind
    require(provider in HOSTED_DEFAULTS, 'Choose a hosted provider: OpenRouter, Google, OpenAI, NanoGPT, NovelAI or other.', 422)
    return provider


def concurrency_for(kind, requested, provider=None) -> int:
    """Codex is strictly serial (F8), a local GPU runs one job at a time, and NovelAI makes one picture at a time
    per account."""
    if kind in {'comfyui', 'codex'} or provider == 'novelai':
        return 1
    return requested or 2


def create(database, vault, body) -> dict:
    provider = provider_for(body.kind, body.provider)
    config = merged_config(body.kind, provider, {}, body)
    allows = int(bool(body.allows_nsfw))
    validate(body.kind, provider, config, body.controlled_machine, allows)
    require_safe_loras({'kind': body.kind, 'provider': provider, 'config': encode(config),
                        'controlled_machine': int(bool(body.controlled_machine)), 'allows_nsfw': allows})
    backend_id = identifier()
    label = body.label or KIND_LABELS.get(body.kind) or HOSTED_DEFAULTS[provider]['label']
    reference = None
    if body.api_key:
        vault.put(credential_ref(backend_id), body.api_key)
        reference = credential_ref(backend_id)
    with database.connect(write=True) as connection:
        timestamp = database.now()
        position = len(ordered(connection))
        row = {'kind': body.kind, 'config': encode(config), 'controlled_machine': int(bool(body.controlled_machine)),
               'provider': provider, 'allows_nsfw': allows, 'blocked_reason': None, 'disclosure_accepted_at': None}
        accepted = timestamp if body.accept_disclosure else None
        enabled = body.enabled if body.enabled is not None else True
        require_disclosure(row, enabled, accepted)
        connection.execute(
            'INSERT INTO image_backends (id, kind, provider, label, enabled, position, config, credential_ref, '
            'controlled_machine, allows_nsfw, concurrency, disclosure_accepted_at, created_at, updated_at) '
            'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (backend_id, body.kind, provider, label, int(enabled), position, encode(config), reference,
             int(bool(body.controlled_machine)), allows, concurrency_for(body.kind, body.concurrency, provider), accepted,
             timestamp, timestamp))
        return view(get(connection, backend_id), connection)


def require_disclosure(backend, enabled, accepted_at):
    if enabled and disclosure(backend) and not accepted_at:
        raise DomainError('Review what this backend receives and accept it before enabling it.', 409,
                          'disclosure_required')


def update(database, vault, backend_id, body) -> dict:
    with database.connect(write=True) as connection:
        backend = get(connection, backend_id)
        config = merged_config(backend['kind'], backend['provider'], decode(backend['config']), body)
        controlled = backend['controlled_machine'] if body.controlled_machine is None else int(body.controlled_machine)
        allows = backend['allows_nsfw'] if body.allows_nsfw is None else int(body.allows_nsfw)
        validate(backend['kind'], backend['provider'], config, controlled, allows)
        timestamp = database.now()
        accepted = timestamp if body.accept_disclosure else backend['disclosure_accepted_at']
        # Sending NSFW requests somewhere new is a new destination for them, so it is accepted again.
        changed_destination = config.get('base_url') != decode(backend['config']).get('base_url') \
            or controlled != backend['controlled_machine'] or allows > backend['allows_nsfw']
        if changed_destination and not body.accept_disclosure:
            accepted = None
        enabled = backend['enabled'] if body.enabled is None else int(body.enabled)
        candidate = {**backend, 'config': encode(config), 'controlled_machine': controlled, 'allows_nsfw': allows}
        require_disclosure(candidate, enabled, accepted)
        require_safe_loras(candidate)
        reference = backend['credential_ref']
        if body.api_key:
            vault.put(credential_ref(backend_id), body.api_key)
            reference = credential_ref(backend_id)
        connection.execute(
            'UPDATE image_backends SET label=?, enabled=?, config=?, credential_ref=?, controlled_machine=?, '
            'allows_nsfw=?, concurrency=?, disclosure_accepted_at=?, blocked_reason=?, updated_at=? WHERE id=?',
            (body.label or backend['label'], enabled, encode(config), reference, controlled, allows,
             concurrency_for(backend['kind'], body.concurrency or backend['concurrency'], backend['provider']), accepted,
             None if body.api_key else backend['blocked_reason'], timestamp, backend_id))
        return view(get(connection, backend_id), connection)


def move(database, backend_id, position) -> list[dict]:
    with database.connect(write=True) as connection:
        rows = ordered(connection)
        moving = next((row for row in rows if row['id'] == backend_id), None)
        require(moving is not None, 'This item could not be found.', 404)
        rows.remove(moving)
        rows.insert(min(position, len(rows)), moving)
        connection.executemany('UPDATE image_backends SET position=? WHERE id=?',
                               [(index, row['id']) for index, row in enumerate(rows)])
        return [view(row, connection) for row in ordered(connection)]


def delete(database, backend_id) -> list[dict]:
    """Jobs keep their recorded backend details; queued ones fail at dispatch."""
    with database.connect(write=True) as connection:
        get(connection, backend_id)
        connection.execute('DELETE FROM image_backends WHERE id=?', (backend_id,))
        return [view(row, connection) for row in ordered(connection)]


def block(database, backend_id, reason):
    with database.connect(write=True) as connection:
        connection.execute('UPDATE image_backends SET blocked_reason=?, updated_at=? WHERE id=?',
                           (reason, database.now(), backend_id))


def unblock(database, backend_id) -> dict:
    with database.connect(write=True) as connection:
        get(connection, backend_id)
        connection.execute('UPDATE image_backends SET blocked_reason=NULL, updated_at=? WHERE id=?',
                           (database.now(), backend_id))
        return view(get(connection, backend_id), connection)
