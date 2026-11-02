"""Headless ComfyUI over its HTTP API (PRD F7).

The app only talks to a ComfyUI server the user configured. It never starts, stops or restarts
one, and cancelling removes or interrupts only the prompt this app queued.

Each backend has a model family (Settings > Images; Vanta, 2026-10-13), and each family a built-in
workflow (FAMILIES), made from Vanta's own TXT2IMG and reference workflows for it (2026-10-13). Krea 2 is
the default, on the files ComfyUI's own Krea 2 template uses (`krea2_turbo_fp8_scaled.safetensors`, the
`qwen3vl_4b_fp8_scaled.safetensors` encoder of type `krea2`, `qwen_image_vae.safetensors`), 8 steps at
CFG 1 with an empty negative. The other families start on their makers' public files. The check reports
any node or model file the server does not have. A custom workflow in ComfyUI's API format can replace a
built-in one, using `{{prompt}}`, `{{negative}}`, `{{seed}}`, `{{width}}` and `{{height}}` where the
request's values belong.

With a built-in workflow the user can pick other files from their server for its loaders
(`unet_name`, `clip_name` with its `type`, and `vae_name`, or a Booru model's `ckpt_name`, in the
backend's config); `files` asks the server which ones it has. Names are kept exactly as the server
lists them, subfolder and all (`Krea 2\\model.safetensors` on Windows). A custom workflow is used
exactly as given.

Onboarding portraits follow an earlier picture. Those use a second workflow with
`{{reference_image}}` (a LoadImage node's image); the app uploads the picture through
`/upload/image` and puts its name there. Each family has a built-in one with the same loader files and
sampler settings; three need a custom node pack, which the check names:
- Krea 2: the Identity Edit LoRA and the comfyui-krea2edit nodes (Apache-2.0, no Python dependencies,
  installable with one press, images/node_packs.py). Its model can be a separate one (`ref_unet_name`);
  a Krea 2 Edit model reads the reference by itself, so with one the LoRA is left out and ref_boost is 2.5.
- Qwen Image 2.1: ComfyUI's own TextEncodeQwenImage21.
- Z-Image Turbo: plain image-to-image (denoise 0.7), core nodes; it keeps the picture's layout and colours.
- Anima: an edit with the Anima Edit LoRA and ApplyCosmosReferenceLatent (ComfyUI-Cosmos-Reference).
- Booru: IP-Adapter Plus (ComfyUI_IPAdapter_plus, with its SDXL ViT-H models).
A custom reference workflow replaces a built-in one.
"""
import asyncio
import json
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

import httpx

from dungeon.errors import DomainError
from dungeon.images import node_packs, tags
from dungeon.images.adapters.base import AdapterError, Check, ImageResult, media_type
from dungeon.providers.urls import is_loopback

WORKFLOWS = Path(__file__).parent.parent / 'workflows'
NUMERIC = {'{{seed}}', '{{width}}', '{{height}}'}
MODEL_KEYS = ('unet_name', 'ckpt_name')
LORA_NODE = 'prospero-lora'
REFERENCE = '{{reference_image}}'
MARKERS = re.compile(r'\{\{(?:prompt|negative|seed|width|height|reference_image)\}\}')
# The built-in workflows' loader inputs the user can choose files for: config key -> (node, input).
FILE_INPUTS = {'unet_name': ('UNETLoader', 'unet_name'), 'clip_name': ('CLIPLoader', 'clip_name'),
               'clip_type': ('CLIPLoader', 'type'), 'vae_name': ('VAELoader', 'vae_name'),
               'ckpt_name': ('CheckpointLoaderSimple', 'ckpt_name'),
               # The reference workflow's own model, where a family has one; unset means the same as unet_name.
               'ref_unet_name': ('UNETLoader', 'unet_name')}
REFERENCE_ONLY = ('ref_unet_name',)
# A .gguf model file loads through the ComfyUI-GGUF nodes' loader instead of UNETLoader (Vanta, 2026-10-28: one node
# swapped), so smaller cards can use GGUF quantizations. Its list holds the .gguf files in diffusion_models and unet.
GGUF_LOADER = 'UnetLoaderGGUF'
# A Krea 2 Edit model reads the reference by itself, so the Identity Edit LoRA is left out for one and
# the reference counts for more (Vanta's Krea 2 Reference workflow, 2026-10-13).
EDIT_MODEL = re.compile(r'edit', re.IGNORECASE)
LORA_INPUT = ('LoraLoaderModelOnly', 'lora_name')
# Custom nodes the built-in workflows use, with where to get them.
NODE_PACKS = {
    **{name: ('Krea 2 Identity Edit', 'https://github.com/lbouaraba/comfyui-krea2edit')
       for name in ('Krea2EditModelPatch', 'Krea2EditGroundedEncode')},
    **{name: ('IPAdapter Plus', 'https://github.com/cubiq/ComfyUI_IPAdapter_plus')
       for name in ('IPAdapterUnifiedLoader', 'IPAdapterAdvanced')},
    'ApplyCosmosReferenceLatent': ('Cosmos Reference', 'https://github.com/Mirumo0u0/ComfyUI-Cosmos-Reference'),
    GGUF_LOADER: ('ComfyUI-GGUF', 'https://github.com/city96/ComfyUI-GGUF')}
# Files a node loads by preset rather than by name: IPAdapter Plus's loader finds its models by name in their
# folders, which its own loader nodes list (src/features/settings/modelFiles.ts PRESET_FILES).
PRESET_FILES = {'IPAdapterUnifiedLoader': (
    ('IPAdapterModelLoader', 'ipadapter_file', 'ip-adapter-plus_sdxl_vit-h.safetensors', 'models/ipadapter'),
    ('CLIPVisionLoader', 'clip_name', 'CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors', 'models/clip_vision'))}
# The built-in workflow's KSampler settings the user can change for their model; unset means the
# workflow's own (Krea 2 Turbo's are 8 steps, CFG 1, euler, simple).
SAMPLER_INPUTS = ('steps', 'cfg', 'sampler_name', 'scheduler')
SAMPLER_LISTS = ('sampler_name', 'scheduler')
SEPARATE = ('unet_name', 'clip_name', 'clip_type', 'vae_name')


@dataclass(frozen=True)
class Family:
    """A kind of image model with a built-in workflow of its own (Vanta, 2026-10-13: not Krea 2 every time).
    `files` are the loader inputs the user picks files for; `matching` says which listed files look like
    this family's (matched on the whole path, so a "Krea 2" folder counts). ComfyUI cannot say a file's
    model family, so `matching` only sorts a list; nothing is hidden for not matching. `reference` is
    None where the family has no way to follow a picture with ComfyUI's own nodes."""
    label: str
    template: str
    reference: str | None
    files: tuple[str, ...]
    matching: dict
    # The character's adopted LoRA is trained on Krea 2 (dungeon/lora/trainer.py), so only Krea 2 applies it.
    character_lora: bool = False
    # The style its prompts start with when the backend has none of its own (images/backends.own_style);
    # None keeps the general one.
    style: str | None = None


QWEN_VAE = re.compile(r'qwen.*vae', re.IGNORECASE)
ANIME = 'Anime illustration'
FAMILIES = {
    'krea2': Family('Krea 2', 'krea2-turbo', 'krea2-turbo-reference', (*SEPARATE, 'ref_unet_name'), {
        'unet_name': re.compile(r'krea|kr2|kera', re.IGNORECASE),
        'ref_unet_name': EDIT_MODEL,
        'clip_name': re.compile(r'qwen[-_ ]?3[-_ ]?vl[-_ ]?4b', re.IGNORECASE),
        'vae_name': re.compile(r'qwen.*vae|krea', re.IGNORECASE),
        'lora': re.compile(r'krea|kr2|kera', re.IGNORECASE)}, character_lora=True),
    # Qwen Image 2.1 (Comfy-Org/Qwen-Image-2.1): the full int8 model at 25 steps, and a reference read by
    # ComfyUI's own TextEncodeQwenImage21, which takes pictures to edit from.
    'qwen21': Family('Qwen Image 2.1', 'qwen-image-2.1', 'qwen-image-2.1-reference', SEPARATE, {
        'unet_name': re.compile(r'qwen[-_ ]?image[-_ ]?2[._-]?1', re.IGNORECASE),
        'clip_name': re.compile(r'qwen[-_ ]?3[-_ ]?vl[-_ ]?8b', re.IGNORECASE),
        'vae_name': re.compile(r'qwen[-_ ]?image[-_ ]?2[._-]?1.*vae', re.IGNORECASE),
        'lora': re.compile(r'qwen', re.IGNORECASE)}),
    # Z-Image Turbo (Tongyi-MAI, Comfy-Org/z_image_turbo): photographic, 9 steps at CFG 1 with an empty negative.
    # It has no edit model yet, so its reference workflow is plain image-to-image at denoise 0.7.
    'zimage': Family('Z-Image Turbo', 'z-image-turbo', 'z-image-turbo-reference', SEPARATE, {
        'unet_name': re.compile(r'z[-_ ]?image', re.IGNORECASE),
        'clip_name': re.compile(r'qwen[-_ ]?3[-_ ]?4b', re.IGNORECASE),
        'vae_name': re.compile(r'(^|[\\/])ae\.safetensors|flux.*vae|z[-_ ]?image', re.IGNORECASE),
        'lora': re.compile(r'z[-_ ]?image|zit', re.IGNORECASE)}),
    # Anima (circlestone-labs/Anima), an anime model: Base v1.0 at 30 steps, CFG 4, with its quality tags. Its
    # reference workflow is an edit: the Anima Edit LoRA and the ComfyUI-Cosmos-Reference pack's node.
    'anima': Family('Anima', 'anima', 'anima-reference', SEPARATE, style=ANIME, matching={
        'unet_name': re.compile(r'anima', re.IGNORECASE),
        'clip_name': re.compile(r'qwen[-_ ]?3[-_ ]?0?[._]?6b', re.IGNORECASE),
        'vae_name': QWEN_VAE,
        'lora': re.compile(r'anima', re.IGNORECASE)}),
    # SDXL and the anime models built on it (Pony, Illustrious, NoobAI): one checkpoint file, clip skip 2. Its
    # reference workflow steers the picture with IP-Adapter Plus (the ComfyUI_IPAdapter_plus pack). Its prompts go
    # out as booru tags (images/tags.py), opening with the quality tags these models were trained on.
    'booru': Family('Booru (SDXL, Pony, Illustrious)', 'booru-sdxl', 'booru-sdxl-reference', ('ckpt_name',),
                    style=tags.ILLUSTRIOUS,
                    matching={
        'ckpt_name': re.compile(r'illustrious|pony|noob|sdxl|xl[-_ .v]|animagine', re.IGNORECASE),
        'lora': re.compile(r'illustrious|pony|noob|sdxl|xl[-_ .v]|pdxl|ilxl', re.IGNORECASE)}),
}
DEFAULT_FAMILY = 'krea2'
# Krea 2's built-in names, which jobs and tests know it by.
TEMPLATE_NAME = FAMILIES[DEFAULT_FAMILY].template
REFERENCE_TEMPLATE_NAME = f'{TEMPLATE_NAME} reference'
TEMPLATE_NAMES = {family.template for family in FAMILIES.values()}


def family_of(config) -> str:
    family = (config or {}).get('family')
    return family if family in FAMILIES else DEFAULT_FAMILY


def has_reference(config) -> bool:
    """Whether this ComfyUI backend can make a picture that follows another: its own reference workflow,
    or its family's built-in one."""
    return bool(config.get('reference_workflow')) or FAMILIES[family_of(config)].reference is not None


def parse_workflow(text: str, reference=False) -> dict:
    try:
        workflow = json.loads(text)
    except json.JSONDecodeError as error:
        raise DomainError('The workflow is not valid JSON. Export it with "Save (API format)".', 422) from error
    if not isinstance(workflow, dict) or not workflow or not all(
            isinstance(node, dict) and 'class_type' in node for node in workflow.values()):
        raise DomainError('The workflow must be in ComfyUI API format: nodes with a class_type each.', 422)
    if '{{prompt}}' not in text:
        raise DomainError('Put {{prompt}} in the workflow where the prompt text belongs.', 422)
    if reference and REFERENCE not in text:
        raise DomainError('Put {{reference_image}} in the reference workflow as the image of a LoadImage node.', 422)
    return workflow


def workflow_for(config, reference=False) -> tuple[dict | None, str]:
    """The workflow to run and its name. A family without a built-in reference workflow has none
    (None) unless the user saved their own."""
    if reference:
        if config.get('reference_workflow'):
            return parse_workflow(config['reference_workflow'], reference=True), 'custom reference'
        family = FAMILIES[family_of(config)]
        if family.reference is None:
            return None, ''
        return built_in(config, reference=True), f'{family.template} reference'
    if config.get('workflow'):
        return parse_workflow(config['workflow']), 'custom'
    return built_in(config), FAMILIES[family_of(config)].template


def built_in(config, reference=False) -> dict | None:
    """The family's built-in workflow (the reference one when asked, None when it has none) with the
    user's chosen loader files and sampler settings in place of its defaults."""
    family = FAMILIES[family_of(config)]
    name = family.reference if reference else family.template
    if name is None:
        return None
    workflow = json.loads((WORKFLOWS / f'{name}.json').read_text(encoding='utf-8'))
    # The reference model comes last, so it replaces the main one in the reference workflow only.
    keys = [key for key in family.files if key not in REFERENCE_ONLY] + \
        ([key for key in family.files if key in REFERENCE_ONLY] if reference else [])
    chosen = [(*FILE_INPUTS[key], file) for key in keys if (file := chosen_file(config, key))]
    chosen += [('KSampler', key, config[key]) for key in SAMPLER_INPUTS if config.get(key) not in (None, '')]
    for class_type, field, value in chosen:
        for node in workflow.values():
            if node['class_type'] == class_type:
                node['inputs'][field] = value
    if reference and EDIT_MODEL.search(config.get('ref_unet_name') or ''):
        without_identity_lora(workflow)
    for node in workflow.values():
        if node['class_type'] == 'UNETLoader' and str(node['inputs'].get('unet_name', '')).lower().endswith('.gguf'):
            node['class_type'] = GGUF_LOADER
            node['inputs'] = {'unet_name': node['inputs']['unet_name']}
    return workflow


def fit_problems(missing: list[str], config) -> list[str]:
    """The raw loader line for the model the app picked for the graphics card, when ComfyUI lacks it, said plainly
    instead (`fit_line`, from dungeon/images/routes.py; Iris, 2026-10-28)."""
    fit = config.get('unet_fit')
    if not fit or config.get('unet_name') or not config.get('fit_line'):
        return missing
    raw = {f'Missing file or option for {loader}.unet_name: {fit}.' for loader in ('UNETLoader', GGUF_LOADER)}
    return [config['fit_line'] if line in raw else line for line in missing]


def chosen_file(config, key) -> str | None:
    """The user's file for a loader input; for the model, else the one the app picked for this computer's graphics
    card (`unet_fit`, dungeon/hardware.py fit_images)."""
    return config.get(key) or (config.get('unet_fit') if key == 'unet_name' else None)


def without_identity_lora(workflow: dict):
    """The Krea 2 reference workflow for an Edit model: its LoRA node taken out, and the reference boosted."""
    for key, node in list(workflow.items()):
        if node['class_type'] == 'LoraLoaderModelOnly':
            source = node['inputs']['model']
            del workflow[key]
            for other in workflow.values():
                for field, value in other['inputs'].items():
                    if value == [key, 0]:
                        other['inputs'][field] = source
    for node in workflow.values():
        if node['class_type'] == 'Krea2EditModelPatch':
            node['inputs']['ref_boost'] = 2.5


def default_sampler(family=DEFAULT_FAMILY) -> dict:
    sampler = next(node for node in built_in({'family': family}).values() if node['class_type'] == 'KSampler')
    return {key: sampler['inputs'][key] for key in SAMPLER_INPUTS}


def default_files(family=DEFAULT_FAMILY) -> dict:
    """The family's own file for each of its loader inputs."""
    workflow = built_in({'family': family})
    # The reference model's default is the main one: empty, "the same".
    return {key: '' if key in REFERENCE_ONLY else next(node['inputs'][FILE_INPUTS[key][1]] for node in workflow.values()
                      if node['class_type'] == FILE_INPUTS[key][0]) for key in FAMILIES[family].files}


def model_file(config) -> str:
    """The diffusion model or checkpoint the built-in workflow loads."""
    family = family_of(config)
    key = 'ckpt_name' if 'ckpt_name' in FAMILIES[family].files else 'unet_name'
    return chosen_file(config, key) or default_files(family)[key]


def options_of(spec) -> list | None:
    """The choices of a combo input in /object_info: `[[...], {...}]`, or `["COMBO", {"options": [...]}]`
    in newer ComfyUI versions. None for any other kind of input."""
    if not isinstance(spec, list) or not spec:
        return None
    if isinstance(spec[0], list):
        return spec[0]
    if spec[0] == 'COMBO' and len(spec) > 1 and isinstance(spec[1], dict) and isinstance(spec[1].get('options'), list):
        return spec[1]['options']
    return None


def input_options(info, class_type, name) -> list[str]:
    inputs = (info.get(class_type) or {}).get('input') or {}
    spec = {**(inputs.get('optional') or {}), **(inputs.get('required') or {})}.get(name)
    return [option for option in options_of(spec) or [] if isinstance(option, str)]


def fill(value, values: dict):
    if isinstance(value, dict):
        return {key: fill(item, values) for key, item in value.items()}
    if isinstance(value, list):
        return [fill(item, values) for item in value]
    if isinstance(value, str):
        if value in NUMERIC:
            return values[value]
        # One pass, so a "{{negative}}" the user wrote inside their appearance is never filled in turn, and a number
        # inside a longer value ("x_{{seed}}") is written as text.
        return MARKERS.sub(lambda found: str(values[found.group(0)]), value)
    return value


def with_lora(graph: dict, lora: dict, node=LORA_NODE, source=None) -> dict:
    """Insert a LoraLoaderModelOnly after the workflow's model loader (or after `source`, an
    earlier LoRA) and point everything that used that model at it instead. LoKr files load
    through the same node."""
    source = source or next((node_id for node_id, item in graph.items()
                             if any(key in item.get('inputs', {}) for key in MODEL_KEYS)), None)
    if source is None:
        raise AdapterError('incompatible', 'The workflow has no model loader to attach the LoRA to.')
    rewired = {node_id: {**item, 'inputs': {key: [node, 0] if value == [source, 0] else value
                                            for key, value in item.get('inputs', {}).items()}}
               for node_id, item in graph.items()}
    rewired[node] = {'class_type': 'LoraLoaderModelOnly', 'inputs': {
        'model': [source, 0], 'lora_name': lora['comfy_name'], 'strength_model': lora['strength']}}
    return rewired


def with_loras(graph: dict, character: dict | None, styles: list[dict]) -> dict:
    """The character's LoRA first, so its likeness always applies, then each style LoRA after it."""
    source = None
    if character:
        graph, source = with_lora(graph, character), LORA_NODE
    for index, style in enumerate(styles, start=1):
        node = f'prospero-style-lora-{index}'
        graph = with_lora(graph, {'comfy_name': style['name'], 'strength': style['strength']}, node, source)
        source = node
    return graph


def style_loras(config, character: dict | None) -> list[dict]:
    """The backend's style LoRAs, leaving out the character's own file so it is never applied twice."""
    skip = character and character.get('comfy_name')
    return [lora for lora in config.get('style_loras') or [] if lora.get('name') and lora['name'] != skip]


def triggered(prompt: str, character: dict | None, styles: list[dict]) -> str:
    words = [character['trigger']] if character and character.get('trigger') else []
    words += [style['trigger'] for style in styles if style.get('trigger')]
    return ', '.join([*words, prompt])


def family_first(key: str, options: list[str], family=DEFAULT_FAMILY) -> tuple[list[str], list[str]]:
    """The list with the family's files first, and which those are."""
    pattern = FAMILIES[family].matching.get(key)
    found = [option for option in options if pattern and pattern.search(option)]
    return found + [option for option in options if option not in found], found


def output_images(entry) -> list[dict]:
    images = []
    for output in (entry.get('outputs') or {}).values():
        images += [image for image in output.get('images', []) if image.get('type', 'output') == 'output']
    return images


# A workflow of the user's own that loads a tag-trained checkpoint gets tags too, whatever family the backend says.
TAG_MODEL = re.compile(r'illustrious|noob|pony|pdxl|animagine|ilxl', re.IGNORECASE)


def tag_kind(config) -> str | None:
    """'illustrious' or 'pony' when this backend's prompts go out as booru tags (images/tags.py): the Booru family, or
    a workflow of the user's own on another family that loads such a checkpoint. None keeps the paragraph."""
    family = family_of(config)
    if family == 'booru':
        return tags.flavor(config)
    own = ' '.join(str(config.get(key) or '') for key in ('workflow', 'reference_workflow'))
    if family == 'anima' or not TAG_MODEL.search(own):
        return None
    return tags.flavor({'ckpt_name': own})


def worded(config, request, styles) -> tuple[str, str]:
    """The prompt and negative prompt as this backend's model reads them best."""
    kind = tag_kind(config)
    if kind is None:
        return triggered(request.prompt, request.lora, styles), request.negative
    style = config.get('style') or FAMILIES[family_of(config)].style
    prompt, negative = tags.convert(request.prompt, request.negative, None, style, kind)
    return triggered(prompt, request.lora, styles), negative


def failure_text(entry) -> str:
    for message in (entry.get('status') or {}).get('messages', []):
        if isinstance(message, list) and message and message[0] == 'execution_error':
            detail = message[1] if len(message) > 1 and isinstance(message[1], dict) else {}
            return f"ComfyUI could not run the workflow: {detail.get('exception_message', 'unknown error')}".strip()
    return 'ComfyUI reported an error running the workflow.'


class ComfyAdapter:
    def __init__(self, transport: httpx.AsyncBaseTransport | None = None, poll_seconds=1.0, timeout_seconds=900):
        self.transport = transport
        self.poll_seconds = poll_seconds
        self.timeout_seconds = timeout_seconds

    def client(self, base_url):
        return httpx.AsyncClient(base_url=base_url, transport=self.transport, timeout=30, trust_env=False,
                                 follow_redirects=False)

    async def generate(self, request) -> ImageResult:
        workflow, name = workflow_for(request.config, reference=request.reference is not None)
        if workflow is None:
            raise AdapterError('incompatible', f"The built-in {FAMILIES[family_of(request.config)].label} workflow cannot "
                               'follow a reference picture. Add a reference workflow in Settings > Images.')
        if name in TEMPLATE_NAMES and any(request.config.get(key) not in (None, '') for key in SAMPLER_INPUTS):
            used = {**default_sampler(family_of(request.config)), **{key: request.config[key] for key in SAMPLER_INPUTS
                                             if request.config.get(key) not in (None, '')}}
            name = f"{name} ({used['steps']} steps, CFG {used['cfg']:g}, {used['sampler_name']}/{used['scheduler']})"
        styles = style_loras(request.config, request.lora)
        prompt, negative = worded(request.config, request, styles)
        values = {'{{prompt}}': prompt, '{{negative}}': negative, '{{seed}}': request.seed,
                  '{{width}}': request.width, '{{height}}': request.height, REFERENCE: ''}
        async with self.client(request.config['base_url']) as client:
            if request.reference is not None:
                values[REFERENCE] = await self.upload(client, request)
            graph = fill(workflow, values)
            if request.lora or styles:
                graph = with_loras(graph, request.lora, styles)
            if request.lora:
                name = f"{name} + LoRA {request.lora['comfy_name']}"
            for style in styles:
                name = f"{name} + style LoRA {style['name']} at {style['strength']:g}"
            prompt_id = await self.submit(client, graph)
            try:
                async with asyncio.timeout(self.timeout_seconds):
                    entry = await self.wait(client, prompt_id)
            except TimeoutError as error:
                await self.withdraw(client, prompt_id)
                raise AdapterError('timeout', 'ComfyUI did not finish within the time limit; the request was '
                                   'withdrawn.', prompt_id) from error
            except asyncio.CancelledError:
                await self.withdraw(client, prompt_id)
                raise
            images = output_images(entry)
            if not images:
                raise AdapterError('invalid_output', 'The workflow finished without saving an image. It needs a '
                                   'SaveImage node.', prompt_id)
            image = images[0]
            response = await self.call(client, 'GET', '/view', params={
                'filename': image['filename'], 'subfolder': image.get('subfolder', ''), 'type': 'output'})
        return ImageResult(response.content, model=self.model_name(workflow), workflow=name, seed=request.seed,
                           remote_id=prompt_id)

    @staticmethod
    def model_name(workflow) -> str | None:
        for node in workflow.values():
            for key in MODEL_KEYS:
                if isinstance(node.get('inputs', {}).get(key), str):
                    return node['inputs'][key]
        return None

    async def call(self, client, method, path, **kwargs) -> httpx.Response:
        try:
            response = await client.request(method, path, **kwargs)
        except httpx.RequestError as error:
            raise AdapterError('unavailable', 'Cannot reach the ComfyUI server. Check that it is running at the '
                               'configured address.') from error
        if response.status_code >= 500:
            raise AdapterError('failed', f'ComfyUI returned HTTP {response.status_code}.')
        return response

    async def upload(self, client, request) -> str:
        """Put the reference picture in ComfyUI's input folder under this job's own name."""
        extension, kind = media_type(request.reference)
        response = await self.call(client, 'POST', '/upload/image', data={'overwrite': 'true'},
                                   files={'image': (f'prospero-{request.job_id}.{extension}', request.reference, kind)})
        body = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
        if not response.is_success or not isinstance(body.get('name'), str):
            raise AdapterError('failed', f'ComfyUI did not accept the reference picture (HTTP {response.status_code}).')
        return f"{body['subfolder']}/{body['name']}" if body.get('subfolder') else body['name']

    async def submit(self, client, graph) -> str:
        response = await self.call(client, 'POST', '/prompt', json={'prompt': graph, 'client_id': uuid4().hex})
        body = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
        if response.status_code == 400 or body.get('node_errors'):
            error = (body.get('error') or {}).get('message') if isinstance(body.get('error'), dict) else None
            raise AdapterError('incompatible', f"ComfyUI rejected the workflow: {error or 'invalid workflow'}. "
                               'Run the compatibility check in Settings.')
        if not response.is_success or 'prompt_id' not in body:
            raise AdapterError('failed', f'ComfyUI did not accept the request (HTTP {response.status_code}).')
        return body['prompt_id']

    async def wait(self, client, prompt_id) -> dict:
        while True:
            response = await self.call(client, 'GET', f'/history/{prompt_id}')
            entry = response.json().get(prompt_id) if response.is_success else None
            status = (entry or {}).get('status') or {}
            if status.get('status_str') == 'error':
                raise AdapterError('failed', failure_text(entry), prompt_id)
            if entry and (status.get('completed') or output_images(entry)):
                return entry
            await asyncio.sleep(self.poll_seconds)

    async def withdraw(self, client, prompt_id):
        """Remove our prompt if it is still pending, or interrupt it if it is the one running.
        Someone else's prompt is never touched."""
        try:
            queue = (await client.get('/queue')).json()
            if any(len(item) > 1 and item[1] == prompt_id for item in queue.get('queue_pending', [])):
                await client.post('/queue', json={'delete': [prompt_id]})
            elif any(len(item) > 1 and item[1] == prompt_id for item in queue.get('queue_running', [])):
                await client.post('/interrupt', json={'prompt_id': prompt_id})
        except (httpx.HTTPError, ValueError):
            pass

    @staticmethod
    def lora_problems(info, lora_name, styles=()) -> list[str]:
        """The adopted LoRA and each style LoRA must be in ComfyUI's loras folder under the name
        images will ask for."""
        wanted = [(f'The adopted LoRA {lora_name}', lora_name)] if lora_name else []
        wanted += [(f"The style LoRA {style['name']}", style['name']) for style in styles]
        if not wanted:
            return []
        spec = info.get('LoraLoaderModelOnly')
        if spec is None:
            return ['Missing node: LoraLoaderModelOnly, which applies LoRAs.']
        options = options_of((spec.get('input', {}).get('required') or {}).get('lora_name'))
        return [f"{label} is not in ComfyUI's loras folder." for label, name in wanted
                if options is not None and name not in options]

    @staticmethod
    def node_problems(info, workflow) -> list[str]:
        missing = []
        for node in workflow.values():
            spec = info.get(node['class_type'])
            if spec is None:
                pack = NODE_PACKS.get(node['class_type'])
                where = f'from the {pack[0]} nodes, {pack[1]}' if pack else 'install the custom node that provides it'
                problem = f"Missing node: {node['class_type']} ({where})."
                if problem not in missing:
                    missing.append(problem)
                continue
            required = {**(spec.get('input', {}).get('required') or {}), **(spec.get('input', {}).get('optional') or {})}
            for key_name, value in node.get('inputs', {}).items():
                options = options_of(required.get(key_name))
                # A placeholder such as {{reference_image}} is filled in per request.
                if isinstance(value, str) and '{{' not in value and options is not None and value not in options:
                    missing.append(f'Missing file or option for {node["class_type"]}.{key_name}: {value}.')
            for loader, field, file, folder in PRESET_FILES.get(node['class_type'], ()):
                if loader in info and not any(option.endswith(file) for option in input_options(info, loader, field)):
                    missing.append(f'Missing file for {node["class_type"]}: {file} (in {folder}).')
        return missing

    async def check(self, backend, config, key=None) -> Check:
        """Ask the server which nodes and model files it has; nothing is queued or downloaded."""
        try:
            workflow, name = workflow_for(config)
            reference = workflow_for(config, reference=True)[0] or {}
        except DomainError as error:
            return Check(False, error.message)
        try:
            async with self.client(config['base_url']) as client:
                response = await self.call(client, 'GET', '/object_info')
                info = response.json()
        except (AdapterError, ValueError) as error:
            return Check(False, getattr(error, 'message', 'ComfyUI returned an unreadable node list.'))
        missing = self.node_problems(info, workflow)
        # Only a server on this computer can have nodes installed into it.
        packs = node_packs.providing([node['class_type'] for node in [*workflow.values(), *reference.values()]
                                      if node['class_type'] not in info]) \
            if is_loopback(urlsplit(config['base_url']).hostname) else []
        # Problems the two workflows share (the built-in ones' loaders) are listed once.
        follows = [f'Reference workflow: {problem}' for problem in self.node_problems(info, reference)
                   if problem not in missing]
        # The adopted LoRA is a Krea 2 one, used only by Krea 2 (Family.character_lora).
        character = config.get('lora_name') if FAMILIES[family_of(config)].character_lora else None
        missing += self.lora_problems(info, character,
                                      style_loras(config, {'comfy_name': config.get('lora_name')}))
        if config.get('reference_workflow'):
            missing += follows
        missing = fit_problems(missing, config)
        # Users never see the template's file name, so it reads as "the built-in workflow".
        shown = f'built-in {FAMILIES[family_of(config)].label}' if name in TEMPLATE_NAMES else name
        if missing:
            return Check(False, f'ComfyUI is reachable, but the {shown} workflow cannot run yet.', missing, packs)
        if follows:
            # Only profile pictures need the reference workflow, so the backend still passes (Iris's wording).
            pack_nodes = {node for pack in packs for node in node_packs.PACKS[pack['id']]['nodes']}
            needs = ' and '.join(f"the {pack['label']} nodes" for pack in packs)
            others = [line for line in follows if not any(f'Missing node: {node} ' in line for node in pack_nodes)]
            if needs and not others:
                tail = f'Pictures made from a reference need {needs} first.'
            elif needs:
                tail = f'Pictures made from a reference need {needs} and the files under Details first.'
            else:
                tail = 'Pictures made from a reference cannot run yet; Details says what is missing.'
            return Check(True, f'ComfyUI has everything the {shown} workflow needs. {tail}', follows, packs)
        return Check(True, f'ComfyUI is reachable and has every node and model the {shown} workflow uses.')

    async def folder_paths(self, config) -> dict:
        """Where ComfyUI keeps each kind of file, from its own `/internal/folder_paths`."""
        async with self.client(config['base_url']) as client:
            response = await self.call(client, 'GET', '/internal/folder_paths')
        try:
            return response.json() if response.status_code == 200 else {}
        except ValueError:
            return {}

    async def files(self, config) -> dict:
        """The files the server offers the built-in workflow's loaders, asked of the configured
        address with the same client as the check. Nothing is queued or downloaded."""
        found = {}
        inputs = {key: FILE_INPUTS[key] for key in FAMILIES[family_of(config)].files}
        async with self.client(config['base_url']) as client:
            loaders = [class_type for class_type, _ in inputs.values()]
            # A server without the ComfyUI-GGUF nodes answers 404 for their loader, which lists nothing.
            for class_type in dict.fromkeys([*loaders, *([GGUF_LOADER] if 'UNETLoader' in loaders else []),
                                             LORA_INPUT[0], 'KSampler']):
                response = await self.call(client, 'GET', f'/object_info/{class_type}')
                try:
                    found[class_type] = response.json() if response.is_success else {}
                except ValueError as error:
                    raise AdapterError('failed', 'ComfyUI returned an unreadable node list.') from error
                if not isinstance(found[class_type], dict):
                    raise AdapterError('failed', 'ComfyUI returned an unreadable node list.')
        lists = {**inputs, 'lora': LORA_INPUT, **{key: ('KSampler', key) for key in SAMPLER_LISTS}}
        listed = {key: input_options(found[class_type], class_type, name) for key, (class_type, name) in lists.items()}
        for key in ('unet_name', 'ref_unet_name'):
            if key in listed:
                listed[key] += [name for name in input_options(found.get(GGUF_LOADER, {}), GGUF_LOADER, 'unet_name')
                                if name not in listed[key]]
        return listed
