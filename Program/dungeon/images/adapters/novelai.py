"""NovelAI's own image API, with the user's persistent API token (a hosted provider, PRD F9).

NovelAI is not OpenAI-style: `POST {base}/ai/generate-image` takes NovelAI's own parameters and answers with a ZIP
holding the PNG. Its models are trained on booru tags, so the prompt goes through the same tag treatment as a Booru
ComfyUI family. The request shapes follow Vanta's ImageGen client, which was checked against novelai.net's own
requests (V4 and V4.5 send `v4_prompt` captions with `params_version` 3; V5 uses `params_version` 4 with string
preset ids). Check reads `GET /user/subscription`, which spends nothing.

A single 832x1216 (or 1216x832, 1024x1024) picture at 28 steps stays inside an Opus plan's free allowance, so the
sizes and steps here are those; anything else would spend Anlas.
"""
import asyncio
import io
import zipfile

import httpx

from dungeon.images.adapters.base import AdapterError, Check

BASE_URL = 'https://image.novelai.net'
DEFAULT_MODEL = 'nai-diffusion-4-5-full'
MODELS = [
    {'id': 'nai-diffusion-4-5-full', 'name': 'NAI Diffusion V4.5 (Full)'},
    {'id': 'nai-diffusion-4-5-curated', 'name': 'NAI Diffusion V4.5 (Curated)'},
    {'id': 'nai-diffusion-5-full', 'name': 'NAI Diffusion V5 (Full)'},
    {'id': 'nai-diffusion-5-curated', 'name': 'NAI Diffusion V5 (Curated)'},
    {'id': 'nai-diffusion-4-full', 'name': 'NAI Diffusion V4 (Full)'},
    {'id': 'nai-diffusion-4-curated-preview', 'name': 'NAI Diffusion V4 (Curated)'},
    {'id': 'nai-diffusion-3', 'name': 'NAI Diffusion V3 (Anime)'},
    {'id': 'nai-diffusion-furry-3', 'name': 'NAI Diffusion V3 (Furry)'},
]
SIZES = {'square': (1024, 1024), 'landscape': (1216, 832), 'portrait': (832, 1216)}
STEPS = 28
SCALE = 5.0
SAMPLER = 'k_euler_ancestral'
TIERS = {0: 'Paper', 1: 'Tablet', 2: 'Scroll', 3: 'Opus'}
# NovelAI runs one picture at a time per account and answers 429 to a second; a short wait usually clears it.
RETRIES = 2
MAX_WAIT = 10.0


def fit(width: int, height: int) -> tuple[int, int]:
    """NovelAI's free size with the same shape as the one asked for."""
    shape = 'portrait' if height > width else 'landscape' if width > height else 'square'
    return SIZES[shape]


def is_v5(model: str) -> bool:
    return model.startswith('nai-diffusion-5')


def is_v4(model: str) -> bool:
    return model.startswith('nai-diffusion-4')


def captions(prompt: str, negative: str) -> tuple[dict, dict]:
    return ({'caption': {'base_caption': prompt, 'char_captions': []}, 'use_coords': False, 'use_order': True},
            {'caption': {'base_caption': negative, 'char_captions': []}, 'legacy_uc': False})


def parameters(model: str, prompt: str, negative: str, seed: int, width: int, height: int) -> dict:
    """NovelAI's generation parameters for one picture. No quality or UC preset is applied: they add text the
    prompt never asked for, and the prompt's own opening (the backend's style) carries the quality tags."""
    shared = {'width': width, 'height': height, 'scale': SCALE, 'sampler': SAMPLER, 'steps': STEPS, 'n_samples': 1,
              'seed': seed % 2**32, 'negative_prompt': negative, 'noise_schedule': 'native', 'cfg_rescale': 0,
              'dynamic_thresholding': False, 'add_original_image': True, 'legacy': False, 'controlnet_strength': 1,
              # The corrected Euler Ancestral that novelai.net sends.
              'deliberate_euler_ancestral_bug': False, 'prefer_brownian': True}
    positive, avoid = captions(prompt, negative)
    if is_v5(model):
        return {**shared, 'params_version': 4, 'ucPresetId': 'heavy', 'autoSmea': False, 'use_coords': False,
                'legacy_uc': False, 'legacy_v3_extend': False, 'normalize_reference_strength_multiple': True,
                'inpaintImg2ImgStrength': 1, 'characterPrompts': [], 'straight_alpha': True,
                'v4_prompt': positive, 'v4_negative_prompt': avoid}
    shared.update({'qualityToggle': False, 'ucPreset': 0, 'sm': False, 'sm_dyn': False})
    if is_v4(model):
        return {**shared, 'params_version': 3, 'use_coords': False, 'v4_prompt': {**positive, 'legacy_uc': False},
                'v4_negative_prompt': {**avoid, 'use_coords': False, 'use_order': False}}
    return shared


def body(model: str, prompt: str, negative: str, seed: int, width: int, height: int) -> dict:
    width, height = fit(width, height)
    return {'input': prompt, 'model': model, 'action': 'generate',
            'parameters': parameters(model, prompt, negative, seed, width, height)}


def first_image(data: bytes) -> bytes:
    """The picture in NovelAI's ZIP answer."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names = sorted(name for name in archive.namelist()
                           if name.lower().endswith(('.png', '.webp', '.jpg', '.jpeg')))
            if not names:
                raise AdapterError('invalid_output', 'NovelAI answered without a picture.')
            return archive.read(names[0])
    except zipfile.BadZipFile as error:
        raise AdapterError('invalid_output', 'NovelAI returned an unreadable answer.') from error


def wait_for(response: httpx.Response, attempt: int) -> float:
    try:
        wait = float(response.headers.get('retry-after', ''))
    except ValueError:
        wait = 2.0 ** attempt
    return min(max(wait, 0.0), MAX_WAIT)


def failure(response: httpx.Response, detail: str) -> AdapterError:
    status = response.status_code
    if status in (401, 403):
        return AdapterError('auth', f'NovelAI rejected the API token (HTTP {status}). Update it in Settings.{detail}')
    if status == 402:
        return AdapterError('failed', 'NovelAI needs an active subscription or Anlas for this picture. An Opus plan '
                                      f'makes these pictures for free.{detail}')
    if status == 429:
        return AdapterError('rate_limited', f'NovelAI is busy with another picture on this account. Try again '
                                            f'shortly.{detail}')
    return AdapterError('failed', f'NovelAI rejected the request (HTTP {status}).{detail}')


async def generate(client: httpx.AsyncClient, base_url: str, key: str, payload: dict, said) -> bytes:
    headers = {'Authorization': f'Bearer {key}', 'Accept': 'application/x-zip-compressed'}
    for attempt in range(RETRIES + 1):
        try:
            response = await client.post(base_url + '/ai/generate-image', headers=headers, json=payload)
        except httpx.TimeoutException as error:
            raise AdapterError('timeout', 'NovelAI did not answer within the time limit.') from error
        except httpx.RequestError as error:
            raise AdapterError('unavailable', 'Cannot reach NovelAI. Check your network.') from error
        if response.status_code == 429 and attempt < RETRIES:
            await asyncio.sleep(wait_for(response, attempt + 1))
            continue
        if response.is_success:
            return first_image(response.content)
        raise failure(response, said(response.text[:2000]))
    raise AdapterError('rate_limited', 'NovelAI is busy with another picture on this account.')  # pragma: no cover


async def check(client: httpx.AsyncClient, base_url: str, key: str | None, model: str | None) -> Check:
    """Reads the account's plan with the token; makes nothing and spends nothing."""
    if not key:
        return Check(False, 'Add your NovelAI API token (Account Settings > Get Persistent API Token on novelai.net).')
    try:
        response = await client.get(base_url + '/user/subscription', headers={'Authorization': f'Bearer {key}'})
    except httpx.RequestError:
        return Check(False, 'Cannot reach NovelAI.')
    if response.status_code in (401, 403):
        return Check(False, 'NovelAI rejected the API token.')
    if not response.is_success:
        return Check(False, f'NovelAI answered HTTP {response.status_code} when reading the account.')
    try:
        account = response.json()
    except ValueError:
        account = {}
    account = account if isinstance(account, dict) else {}
    if model and model not in {item['id'] for item in MODELS}:
        return Check(False, f'The token works, but {model} is not a NovelAI image model this app knows.')
    tier = TIERS.get(account.get('tier'), 'unknown')
    if not account.get('active'):
        return Check(False, 'The token works, but this NovelAI account has no active subscription.',
                     ['NovelAI makes pictures for subscribers. Pictures would spend Anlas, if the account has any.'])
    details = [f'Plan: {tier}.']
    if tier == 'Opus':
        details.append('Pictures here are one at a time at normal size and 28 steps, which Opus makes for free.')
    else:
        details.append('Each picture spends Anlas on this plan. Opus makes them for free.')
    return Check(True, 'The token works. Image output itself is not tested until you make an image.', details)
