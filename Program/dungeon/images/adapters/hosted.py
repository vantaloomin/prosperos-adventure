"""Hosted image APIs with the user's own key (PRD F9).

Four request shapes cover the tested providers:

- `images`: OpenAI-style `POST /images/generations`, used by the OpenAI API and Google's
  OpenAI-compatible endpoint for its image models.
- OpenRouter's own image API, `POST /images` with an aspect ratio, for every image model it lists at
  `/images/models` (FLUX, Seedream, Recraft and the rest, not only the Google and OpenAI models that
  also write text). Any backend at openrouter.ai uses it, whatever style it was saved with.
- NovelAI's own API (`provider` 'novelai', adapters/novelai.py), with booru-tag prompts.
- `chat`: `POST /chat/completions` with `modalities: ["image", "text"]`, which returns the picture as
  a data URL in `message.images`; OpenRouter backends used it before its image API.

A request carries only the prompt (X2), except an onboarding portrait, which also carries the
picture it follows: in the chat message, or as the image of an OpenAI `/images/edits` request. Provider-reported usage is recorded as given; unknown
cost stays unknown. A provider's content refusal is reported as `refused`, which reclassifies the
request as NSFW so it is never offered to another hosted provider (F6).
"""
import base64
import json
import math
import re
from urllib.parse import urlsplit

import httpx

from dungeon.images.adapters import novelai
from dungeon.images.adapters.base import AdapterError, Check, ImageResult, media_type
from dungeon.providers.urls import network

REFUSAL_SIGNS = ('content_policy', 'content policy', 'safety', 'moderation', 'prohibited', 'blocked', 'nsfw')
TIMEOUT_SECONDS = 180
# Request paths people paste with the base URL from a provider's docs; the adapter adds them itself.
# How Google's and OpenAI's image models are named, since their model lists do not say what each outputs.
IMAGE_WORDS = ('image', 'imagen', 'dall-e')
ENDPOINT_SUFFIXES = ('/images/generations', '/images/edits', '/images/edit', '/chat/completions', '/images/models',
                     '/models', '/images')
# The shapes OpenRouter's image API names; each model takes the nearest it offers.
ASPECT_RATIOS = ('1:1', '4:3', '3:4', '3:2', '2:3', '16:9', '9:16', '4:5', '5:4')
# Whether each OpenRouter image model reads a picture as input, by id, from the last time the list was read.
OPENROUTER_REFERENCES: dict[str, bool] = {}


def api_base(value: str) -> str:
    """The API base without a trailing request path, so a URL copied from an endpoint's docs (say
    `https://nano-gpt.com/api/v1/images/generations`) still works. Applied when saving and again
    when calling, for backends saved before this."""
    value = value.strip().rstrip('/')
    for suffix in ENDPOINT_SUFFIXES:
        if value.endswith(suffix) and urlsplit(value).path != suffix:
            return value.removesuffix(suffix).rstrip('/')
    return value


def refused(text: str) -> bool:
    lowered = text.casefold()
    return any(sign in lowered for sign in REFUSAL_SIGNS)


# Anything in a provider's answer that looks like a key is cut before it is shown or stored.
KEY_LIKE = re.compile(r'\b(?:sk|pk|rk|key|AIza)[-_A-Za-z0-9]{12,}|\b[A-Za-z0-9_-]{32,}\b')


def said(text: str, limit: int = 300) -> str:
    """The provider's own words about a failed request, as ' The provider said: "..."', or '' when there are none:
    `error.message` (OpenAI, OpenRouter, Google), a top-level `message` or `detail`, else short plain text."""
    words = ''
    try:
        data = json.loads(text)
    except ValueError:
        data = None
    if isinstance(data, dict):
        error = data.get('error')
        if isinstance(error, dict):
            error = error.get('message') or error.get('code')
            metadata = (data.get('error') or {}).get('metadata') or {}
            raw = metadata.get('raw') if isinstance(metadata, dict) else None
            if isinstance(raw, str) and raw.strip() and raw.strip() not in str(error):
                error = f'{error} ({raw})'
        words = next((str(item) for item in (error, data.get('message'), data.get('detail')) if item), '')
    elif data is None and text and '<' not in text[:50]:
        words = text
    words = KEY_LIKE.sub('[hidden]', ' '.join(words.split()))
    if not words:
        return ''
    if len(words) > limit:
        words = words[:limit].rstrip() + '…'
    return f' The provider said: "{words}"'


def decode_data_url(url: str) -> bytes:
    header, _, payload = url.partition(',')
    if not header.startswith('data:image/') or ';base64' not in header:
        raise AdapterError('invalid_output', 'The provider returned an image in an unexpected form.')
    return base64.b64decode(payload, validate=False)


def is_openrouter(config) -> bool:
    host = urlsplit(config.get('base_url') or '').hostname or ''
    return host == 'openrouter.ai' or host.endswith('.openrouter.ai')


def aspect_ratio(width: int, height: int) -> str:
    """The listed aspect ratio nearest the size asked for."""
    def distance(ratio):
        wide, high = ratio.split(':')
        return abs(math.log(width / height) - math.log(int(wide) / int(high)))
    return min(ASPECT_RATIOS, key=distance)


def models_url(config, provider) -> str:
    """Where the provider lists its image models. NanoGPT's `/models` lists text models only, so a
    NanoGPT address (chosen by name or entered as another API) uses its image list. OpenRouter's `/models`
    leaves out models that write no text, so its image list is the one with every image model."""
    host = urlsplit(config['base_url']).hostname or ''
    if provider == 'nanogpt' or host == 'nano-gpt.com' or host.endswith('.nano-gpt.com') or is_openrouter(config):
        return config['base_url'] + '/images/models'
    return config['base_url'] + '/models'


def model_entries(data) -> list[dict]:
    """The models a provider lists, in the shapes seen: OpenAI's `{"data": [...]}`, a `{"models": [...]}` list or
    `{"models": {id: {...}}}` table, or a bare list, of records with an `id` (or `model`) or of plain names."""
    if isinstance(data, dict):
        data = data.get('data', data.get('models', []))
    if isinstance(data, dict):
        data = [{'id': key, **(value if isinstance(value, dict) else {})} for key, value in data.items()]
    entries = []
    for item in data if isinstance(data, list) else []:
        item = {'id': item} if isinstance(item, str) else item
        if isinstance(item, dict) and isinstance(item.get('id') or item.get('model'), str):
            entries.append(item)
    return entries


def makes_images(entry: dict) -> bool | None:
    """Whether a listed model answers with images, when the list says (OpenRouter's output modalities)."""
    architecture = entry.get('architecture') if isinstance(entry.get('architecture'), dict) else {}
    modalities = architecture.get('output_modalities') or entry.get('output_modalities')
    return 'image' in modalities if isinstance(modalities, list) else None


def vector_only(entry: dict) -> bool:
    """A model that only draws SVG (Recraft's vector models), which a photo in the app cannot show."""
    formats = entry.get('supported_parameters') if isinstance(entry.get('supported_parameters'), dict) else {}
    formats = formats.get('output_format') if isinstance(formats.get('output_format'), dict) else {}
    return formats.get('values') == ['svg']


def remember_references(entries: list[dict]):
    """Notes which OpenRouter models read a picture, for the onboarding portraits that follow one."""
    for entry in entries:
        architecture = entry.get('architecture') if isinstance(entry.get('architecture'), dict) else {}
        inputs = architecture.get('input_modalities')
        if isinstance(inputs, list):
            OPENROUTER_REFERENCES[str(entry.get('id'))] = 'image' in inputs


def image_models(data, provider) -> list[dict]:
    """The image models in a provider's list, by id. Where the list says what each model outputs, only image
    models; Google's and OpenAI's lists mix text and image models without saying, so their names decide."""
    entries = [entry for entry in model_entries(data) if not vector_only(entry)]
    said = [makes_images(entry) for entry in entries]
    if any(value is not None for value in said):
        entries = [entry for entry, value in zip(entries, said) if value]
    rows = {}
    for entry in entries:
        model_id = str(entry.get('id') or entry.get('model')).removeprefix('models/')
        name = entry.get('name') if isinstance(entry.get('name'), str) and entry['name'].strip() else model_id
        rows.setdefault(model_id, {'id': model_id, 'name': name})
    if provider in ('openai', 'google') and not any(value is not None for value in said):
        rows = {key: row for key, row in rows.items() if any(word in key.lower() for word in IMAGE_WORDS)}
    return sorted(rows.values(), key=lambda row: row['name'].lower())


def takes_reference(config, provider) -> bool:
    """Chat-style image models read a picture in the message and OpenRouter's image API takes one
    beside the prompt, unless its list says the model reads text only; of the `images` style, only the
    OpenAI API's `/images/edits` is a tested shape for one."""
    if provider == 'novelai':
        return False
    if is_openrouter(config):
        return OPENROUTER_REFERENCES.get(config.get('model'), True)
    return config.get('api_style') == 'chat' or provider == 'openai'


def data_url(picture: bytes) -> str:
    _extension, kind = media_type(picture)
    return f"data:{kind};base64,{base64.b64encode(picture).decode('ascii')}"


def chat_content(prompt: str, reference: bytes | None):
    if reference is None:
        return prompt
    return [{'type': 'text', 'text': prompt}, {'type': 'image_url', 'image_url': {'url': data_url(reference)}}]


def openrouter_body(config, prompt: str, request) -> dict:
    """OpenRouter's image API: the size goes as an aspect ratio, which every image model there takes."""
    body = {'model': config['model'], 'prompt': prompt, 'aspect_ratio': aspect_ratio(request.width, request.height)}
    if request.reference is not None:
        body['input_references'] = [{'type': 'image_url', 'image_url': {'url': data_url(request.reference)}}]
    return body


class HostedAdapter:
    def __init__(self, transport: httpx.AsyncBaseTransport | None = None, timeout_seconds=TIMEOUT_SECONDS):
        self.transport = transport
        self.timeout_seconds = timeout_seconds

    def client(self, base_url: str):
        return httpx.AsyncClient(transport=self.transport, timeout=self.timeout_seconds, follow_redirects=False,
                                 **network(base_url))

    async def generate(self, request) -> ImageResult:
        if not request.key:
            raise AdapterError('auth', 'Add your NovelAI API token under Connection below.'
                               if request.backend['provider'] == 'novelai'
                               else 'Add an API key for this provider under Connection below.')
        config, provider = {**request.config, 'base_url': api_base(request.config['base_url'])}, request.backend['provider']
        prompt = f'{request.prompt}\nAvoid: {request.negative}' if request.negative else request.prompt
        headers = {'Authorization': f'Bearer {request.key}'}
        if request.reference is not None and not takes_reference(config, provider):
            raise AdapterError('incompatible', 'This image API cannot make a picture from a reference picture.')
        if provider == 'novelai':
            return await self.novelai(config, request)
        async with self.client(config['base_url']) as client:
            if is_openrouter(config):
                data = await self.post(client, config['base_url'] + '/images', headers,
                                       openrouter_body(config, prompt, request))
                image = await self.images_image(client, data)
            elif config.get('api_style') == 'chat':
                body = {'model': config['model'], 'modalities': ['image', 'text'],
                        'messages': [{'role': 'user', 'content': chat_content(prompt, request.reference)}]}
                data = await self.post(client, config['base_url'] + '/chat/completions', headers, body)
                image = self.chat_image(data)
            elif request.reference is not None:
                data = await self.edit(client, config, headers, prompt, request)
                image = await self.images_image(client, data)
            else:
                body = {'model': config['model'], 'prompt': prompt, 'n': 1, 'size': f'{request.width}x{request.height}'}
                if provider != 'openai':
                    body['response_format'] = 'b64_json'
                # OpenAI's own options, for a caller that sets them (scripts/art/icons.py: transparent icons).
                body |= {name: config[name] for name in ('background', 'quality') if config.get(name)}
                data = await self.post(client, config['base_url'] + '/images/generations', headers, body)
                image = await self.images_image(client, data)
        return ImageResult(image, model=config['model'], workflow=f"{provider} {config.get('api_style')}",
                           usage=data.get('usage') if isinstance(data.get('usage'), dict) else None,
                           remote_id=data.get('id') if isinstance(data.get('id'), str) else None)

    async def novelai(self, config, request) -> ImageResult:
        """NovelAI draws from booru tags: the prompt becomes tags here, after the content check read it as written,
        with the backend's own style as the opening tags."""
        from dungeon.images import tags
        from dungeon.images.adapters.comfyui import FAMILIES
        model = config.get('model') or novelai.DEFAULT_MODEL
        style = config.get('style') or FAMILIES['booru'].style  # as backends.own_style has it
        prompt, negative = tags.convert(request.prompt, request.negative, name=None, style=style,
                                        kind='novelai')
        payload = novelai.body(model, prompt, negative, request.seed, request.width, request.height)
        async with self.client(config['base_url']) as client:
            image = await novelai.generate(client, config['base_url'], request.key, payload, said)
        return ImageResult(image, model=model, workflow='novelai', seed=payload['parameters']['seed'])

    async def edit(self, client, config, headers, prompt, request) -> dict:
        """OpenAI's `/images/edits`: the reference goes up as a file beside the prompt."""
        extension, kind = media_type(request.reference)
        fields = {'model': config['model'], 'prompt': prompt, 'n': '1', 'size': f'{request.width}x{request.height}'}
        files = {'image': (f'reference.{extension}', request.reference, kind)}
        return await self.post(client, config['base_url'] + '/images/edits', headers, None, data=fields, files=files)

    async def post(self, client, url, headers, body, **form) -> dict:
        try:
            response = await client.post(url, headers=headers, **form) if form else \
                await client.post(url, headers=headers, json=body)
        except httpx.TimeoutException as error:
            raise AdapterError('timeout', 'The provider did not answer within the time limit.') from error
        except httpx.RequestError as error:
            raise AdapterError('unavailable', 'Cannot reach the provider. Check the address and your network.') \
                from error
        text = response.text[:2000]
        detail = said(text) if response.status_code >= 400 else ''
        if response.status_code in (401, 403):
            raise AdapterError('auth', f'The provider rejected the API key (HTTP {response.status_code}). Update it in '
                                       f'Settings.{detail}')
        if response.status_code == 429:
            raise AdapterError('rate_limited', f'The provider reached a rate or usage limit. Try again later.{detail}')
        if response.status_code >= 400 and refused(text):
            raise AdapterError('refused', f'The provider refused this image under its content rules.{detail}')
        if not response.is_success:
            raise AdapterError('failed', f'The provider rejected the request (HTTP {response.status_code}).{detail}')
        try:
            data = response.json()
        except ValueError as error:
            raise AdapterError('invalid_output', 'The provider returned an unreadable response.') from error
        if not isinstance(data, dict):
            raise AdapterError('invalid_output', 'The provider returned an unreadable response.')
        return data

    @staticmethod
    def chat_image(data) -> bytes:
        choice = (data.get('choices') or [{}])[0]
        message = choice.get('message') or {}
        for image in message.get('images') or []:
            url = (image.get('image_url') or {}).get('url') if isinstance(image, dict) else None
            if isinstance(url, str):
                return decode_data_url(url)
        refusal, content = str(message.get('refusal') or ''), message.get('content')
        reply = said(json.dumps({'message': refusal or (content if isinstance(content, str) else '')}))
        if choice.get('finish_reason') == 'content_filter' or refused(refusal):
            raise AdapterError('refused', f'The provider refused this image under its content rules.{reply}')
        raise AdapterError('invalid_output', 'The model answered without an image. Check that it is an image '
                                             f'model.{reply}')

    async def images_image(self, client, data) -> bytes:
        item = (data.get('data') or [{}])[0]
        if isinstance(item.get('b64_json'), str):
            return base64.b64decode(item['b64_json'])
        url = item.get('url')
        if isinstance(url, str) and url.startswith('https://'):
            try:
                response = await client.get(url)
            except httpx.RequestError as error:
                raise AdapterError('unavailable', 'Could not download the finished image.') from error
            if response.is_success:
                return response.content
        raise AdapterError('invalid_output', 'The provider answered without an image.')

    async def models(self, provider, config, key=None) -> list[dict]:
        """The provider's image models, listed with the key when there is one. Sends no prompt and spends
        nothing; OpenRouter lists its models without a key."""
        if provider == 'novelai':
            return novelai.MODELS
        config = {**config, 'base_url': api_base(config['base_url'])}
        url = models_url(config, provider)
        try:
            async with self.client(config['base_url']) as client:
                response = await client.get(url, headers={'Authorization': f'Bearer {key}'} if key else {})
        except httpx.RequestError as error:
            raise AdapterError('unavailable', 'Cannot reach the provider at this address.') from error
        if response.status_code in (401, 403):
            raise AdapterError('auth', 'The provider rejected the API key.' if key else
                               'The provider lists its models only with an API key. Enter the key first.')
        if response.status_code in (404, 405):
            raise AdapterError('failed', f'Nothing lists models at {url}. Type the model name instead.')
        if not response.is_success:
            raise AdapterError('failed', f'The provider answered HTTP {response.status_code} when listing models.')
        try:
            data = response.json()
            if is_openrouter(config):
                remember_references(model_entries(data))
            return image_models(data, provider)
        except ValueError as error:
            raise AdapterError('invalid_output', 'The provider returned an unreadable model list.') from error

    async def check(self, backend, config, key=None) -> Check:
        """Lists the provider's models with the key; sends no prompt and spends no image quota."""
        config = {**config, 'base_url': api_base(config['base_url'])}
        if backend.get('provider') == 'novelai':
            async with self.client(config['base_url']) as client:
                return await novelai.check(client, config['base_url'], key, config.get('model'))
        if not key:
            return Check(False, 'Add an API key for this provider.')
        try:
            async with self.client(config['base_url']) as client:
                url = models_url(config, backend.get('provider'))
                response = await client.get(url, headers={'Authorization': f'Bearer {key}'})
        except httpx.RequestError:
            return Check(False, 'Cannot reach the provider at this address.')
        if response.status_code in (401, 403):
            return Check(False, 'The provider rejected the API key.')
        if response.status_code in (404, 405):
            return Check(False, f'Nothing answered at {url}, so the key and model could not be checked.', [
                'Check the API base URL: it should end at the API version (like /v1), without '
                '/images/generations on the end.',
                'Some services have no model list. Making an image is the real test, and Check never blocks it.'])
        if not response.is_success:
            return Check(False, f'The provider answered HTTP {response.status_code} when listing models.')
        try:
            ids = [str(model.get('id', '')).removeprefix('models/') for model in response.json().get('data', [])]
        except (ValueError, AttributeError):
            ids = []
        if config.get('model') and ids and config['model'] not in ids:
            return Check(False, f"The key works, but the provider does not list the model {config['model']}.")
        return Check(True, 'The key works and the provider lists this model. Image output itself is not tested '
                     'until you make an image.')
