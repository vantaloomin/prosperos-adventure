"""Where a classified request may go (PRD F6).

Prohibited requests are refused everywhere. NSFW requests go only to backends that accept them (a
local ComfyUI, or an image API the user switched to take NSFW) and are refused when none is enabled.
Safe requests go to any enabled backend in the user's order. Nothing sends an NSFW request to Codex,
Google or the OpenAI API, or a Prohibited request anywhere.
"""
from dataclasses import dataclass, field

from dungeon.images.backends import accepts_nsfw
from dungeon.images.content import NSFW, PROHIBITED

LOCAL_NEEDED = ('This image was classified NSFW ({reasons}), so it can only be made on a local backend or an '
                'image API switched to take NSFW, and none is enabled. Set one up in Settings to make it.')


@dataclass
class Route:
    backends: list[dict] = field(default_factory=list)
    reason: str = ''
    refusal: str | None = None
    code: str | None = None

    @property
    def target(self) -> dict | None:
        return self.backends[0] if self.backends else None


def eligible(classification, backend) -> bool:
    if classification.tier == PROHIBITED:
        return False
    if classification.tier == NSFW:
        return accepts_nsfw(backend)
    return True


def route(classification, backends: list[dict], requested_id=None, after_id=None) -> Route:
    """`backends` are the enabled ones in the user's order. `requested_id` is a backend the user
    picked; `after_id` limits a fallback to backends after the one that failed."""
    reasons = ', '.join(classification.reasons) or classification.tier
    if classification.tier == PROHIBITED:
        return Route(reason=f'prohibited: {reasons}', code='prohibited',
                     refusal=f'This image cannot be made on any backend: {reasons}.')
    candidates = backends
    if after_id is not None:
        ids = [backend['id'] for backend in backends]
        candidates = backends[ids.index(after_id) + 1:] if after_id in ids else backends
    allowed = [backend for backend in candidates if eligible(classification, backend)]
    if requested_id is not None:
        picked = next((backend for backend in backends if backend['id'] == requested_id), None)
        if picked is None:
            return Route(reason='requested backend is not enabled', code='backend_unavailable',
                         refusal='That backend is not enabled. Choose another one or enable it in Settings.')
        if not eligible(classification, picked):
            return Route(reason=f'{classification.tier}: {reasons}; requested backend takes safe requests only',
                         code='not_eligible',
                         refusal=f'This image was classified NSFW ({reasons}); that backend takes safe requests only.')
        return Route([picked], f'{classification.tier}: chosen by you')
    if allowed:
        detail = 'backends that accept NSFW only' if classification.tier == NSFW else 'any enabled backend'
        return Route(allowed, f'{classification.tier} ({reasons}): {detail}, in your order')
    if classification.tier == NSFW:
        return Route(reason=f'nsfw ({reasons}): no backend that accepts NSFW enabled', code='no_local_backend',
                     refusal=LOCAL_NEEDED.format(reasons=reasons))
    return Route(reason='no backend enabled', code='no_backend',
                 refusal='No image backend is enabled. Set one up in Settings to make images.')
