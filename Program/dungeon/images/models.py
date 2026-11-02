"""Request bodies for image generation (PRD F3–F9)."""
from typing import Literal

from pydantic import Field

from dungeon.models import Input

Kind = Literal['comfyui', 'codex', 'hosted']
Provider = Literal['comfyui', 'codex', 'openrouter', 'google', 'openai', 'nanogpt', 'novelai', 'other']
Aspect = Literal['square', 'landscape', 'portrait']
Family = Literal['krea2', 'qwen21', 'zimage', 'anima', 'booru']
FILE_NAME = r'^[^\x00-\x1f\x7f]*$'


class StyleLora(Input):
    """A LoRA from ComfyUI's loras folder applied after the character's own, with its trigger words."""
    name: str = Field(min_length=1, max_length=300, pattern=FILE_NAME)
    strength: float = Field(default=0.7, ge=-2, le=2)
    trigger: str = Field(default='', max_length=200, pattern=FILE_NAME)


class BackendFields(Input):
    label: str | None = Field(default=None, max_length=80)
    enabled: bool | None = None
    base_url: str | None = Field(default=None, max_length=500)
    model: str | None = Field(default=None, max_length=200)
    # ComfyUI workflow in API format with {{prompt}}, {{negative}}, {{seed}}, {{width}} and {{height}}.
    workflow: str | None = Field(default=None, max_length=200000)
    # A second ComfyUI workflow for pictures that follow an earlier one, with {{reference_image}} too.
    reference_workflow: str | None = Field(default=None, max_length=200000)
    # Files from the ComfyUI server for the built-in workflow's loaders; empty means its default.
    unet_name: str | None = Field(default=None, max_length=300, pattern=FILE_NAME)
    clip_name: str | None = Field(default=None, max_length=300, pattern=FILE_NAME)
    clip_type: str | None = Field(default=None, max_length=60, pattern=FILE_NAME)
    vae_name: str | None = Field(default=None, max_length=300, pattern=FILE_NAME)
    # A Booru (SDXL) model's single checkpoint file.
    ckpt_name: str | None = Field(default=None, max_length=300, pattern=FILE_NAME)
    ref_unet_name: str | None = Field(default=None, max_length=300, pattern=FILE_NAME)
    # ComfyUI: which model family's built-in workflow to run (dungeon/images/adapters/comfyui.py FAMILIES).
    family: Family | None = None
    # The built-in workflow's sampler; a value equal to the workflow's own is stored as unset.
    steps: int | None = Field(default=None, ge=1, le=100)
    cfg: float | None = Field(default=None, ge=0, le=30)
    sampler_name: str | None = Field(default=None, max_length=60, pattern=FILE_NAME)
    scheduler: str | None = Field(default=None, max_length=60, pattern=FILE_NAME)
    # Style LoRAs for ComfyUI, in order; an empty list removes them.
    style_loras: list[StyleLora] | None = Field(default=None, max_length=3)
    # Starts this backend's image prompts in place of the general style; empty uses the general one.
    style: str | None = Field(default=None, max_length=500)
    cli_path: str | None = Field(default=None, max_length=1000)
    api_style: Literal['images', 'chat'] | None = None
    api_key: str | None = Field(default=None, max_length=4000)
    controlled_machine: bool | None = None
    # Image APIs other than Google and OpenAI: also take NSFW requests (the provider's terms apply).
    allows_nsfw: bool | None = None
    concurrency: int | None = Field(default=None, ge=1, le=4)
    accept_disclosure: bool | None = None


class BackendCreate(BackendFields):
    kind: Kind
    provider: Provider | None = None


class ModelProbe(Input):
    """An image API's connection, saved or not, whose model list is wanted. With `backend_id` and no key typed,
    the backend's saved key is used, but only for the address it was saved for."""
    provider: Provider
    base_url: str = Field(default='', max_length=500)
    api_key: str = Field(default='', max_length=500)
    backend_id: str | None = Field(default=None, max_length=64)


class BackendMove(Input):
    position: int = Field(ge=0, le=50)
