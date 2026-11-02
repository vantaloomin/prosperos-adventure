"""What every image adapter receives and returns."""
from dataclasses import dataclass, field
from pathlib import Path

# Output sizes per backend class. Codex and the OpenAI-style APIs accept these three (F8); the
# ComfyUI sizes keep about one megapixel for a local GPU.
SIZES = {
    'comfyui': {'square': (1024, 1024), 'landscape': (1216, 832), 'portrait': (832, 1216)},
    'default': {'square': (1024, 1024), 'landscape': (1536, 1024), 'portrait': (1024, 1536)},
}


def size_for(kind, aspect) -> tuple[int, int]:
    return SIZES.get(kind, SIZES['default'])[aspect]


def media_type(data: bytes) -> tuple[str, str]:
    """(extension, media type) of a PNG, JPEG or WebP picture, from its first bytes."""
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        return 'webp', 'image/webp'
    if data[:3] == b'\xff\xd8\xff':
        return 'jpg', 'image/jpeg'
    return 'png', 'image/png'


@dataclass
class ImageRequest:
    job_id: str
    prompt: str
    negative: str
    seed: int
    width: int
    height: int
    backend: dict
    config: dict
    key: str | None = None
    raw_dir: Path | None = None
    # The adopted LoRA frozen with the job; only a ComfyUI backend applies it.
    lora: dict | None = None
    # A picture the new one must follow (the same person), for backends that take one
    # (backends.takes_reference). Only the onboarding portraits send one.
    reference: bytes | None = None


@dataclass
class ImageResult:
    data: bytes | None = None
    model: str | None = None
    workflow: str | None = None
    # The seed the backend actually used; None where it takes no seed.
    seed: int | None = None
    usage: dict | None = None
    remote_id: str | None = None
    # Where the untouched output was kept, so a failed check never costs a second request (F8).
    raw_path: Path | None = None


@dataclass
class Check:
    """Compatibility report for Settings; never spends generation quota."""
    ok: bool
    summary: str
    details: list[str] = field(default_factory=list)
    # Node packs the app can install for what is missing ({id, label} from node_packs), for an Install button.
    install: list[dict] = field(default_factory=list)

    def view(self) -> dict:
        return {'ok': self.ok, 'summary': self.summary, 'details': self.details, 'install': self.install}


class AdapterError(Exception):
    """`code` decides what happens next: `auth` stops that backend's queue until the user signs in
    again, `refused` reclassifies the request as NSFW (F6), anything else is an ordinary failure."""

    def __init__(self, code: str, message: str, remote_id: str | None = None):
        self.code = code
        self.message = message
        self.remote_id = remote_id
        super().__init__(message)
