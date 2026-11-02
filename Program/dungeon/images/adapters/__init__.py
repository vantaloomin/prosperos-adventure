"""Backend adapters. Each takes a frozen request and returns image bytes or a typed error."""


def default_adapters() -> dict:
    """One adapter per backend kind, as the app uses them; tests pass their own."""
    from dungeon.images.adapters.codex import CodexAdapter
    from dungeon.images.adapters.comfyui import ComfyAdapter
    from dungeon.images.adapters.hosted import HostedAdapter
    return {'comfyui': ComfyAdapter(), 'codex': CodexAdapter(), 'hosted': HostedAdapter()}
