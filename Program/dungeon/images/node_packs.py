"""ComfyUI custom node packs a built-in workflow needs, installed with one press (Settings > Images).

Vanta approved this one exception to "Dungeon never writes into ComfyUI" (2026-10-13). Only a ComfyUI
server on this computer, and only a pack listed here: its files are fetched from the pinned commit,
each checked against its SHA-256 before anything is written, and placed as a new folder in the
custom_nodes folder ComfyUI itself reports. Nothing else in ComfyUI is touched, no Python package is
installed (the packs here need none), and an existing folder is never replaced. ComfyUI loads the
pack on its next start.
"""
import hashlib
import shutil
import uuid
from pathlib import Path

import httpx

from dungeon.errors import DomainError

PACKS = {
    'krea2edit': {
        'label': 'Krea 2 Identity Edit',
        'folder': 'comfyui-krea2edit',
        'page': 'https://github.com/lbouaraba/comfyui-krea2edit',
        'licence': 'Apache-2.0',
        'source': 'https://raw.githubusercontent.com/lbouaraba/comfyui-krea2edit/'
                  '86f886dac23013d88996e3a2e99093ba44d322fb/',
        'nodes': ('Krea2EditModelPatch', 'Krea2EditGroundedEncode'),
        'files': {
            '__init__.py': '43c5f9aa2292bd4174dfe9aca0baa10d82713dafe2e04dd1ba2fde2ce89c3d39',
            'pyproject.toml': 'b1e6f58448f21e417bbf0ad19059a07df11a6b62b7c29fd7121e987c4794be97',
            'LICENSE': 'cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30',
            'README.md': 'ee12b615b305f608115c7466146e26ad4d19915f3f9654047ba3007ad8289834',
        },
    },
}


def providing(node_types) -> list[dict]:
    """The listed packs that provide any of these node types, as {id, label}."""
    wanted = set(node_types)
    return [{'id': pack_id, 'label': pack['label']} for pack_id, pack in PACKS.items() if wanted & set(pack['nodes'])]


# What sits beside custom_nodes in a ComfyUI folder: main.py and comfy/ in a source or portable install, models/ in
# the desktop app's folder. A folder without any of them is not ComfyUI's, whatever the server says.
COMFY_SIGNS = ('main.py', 'comfy', 'models')


def comfyui_nodes_folder(path: Path) -> bool:
    """A folder named custom_nodes inside what looks like a ComfyUI folder."""
    return path.name == 'custom_nodes' and any((path.parent / sign).exists() for sign in COMFY_SIGNS)


def custom_nodes_folder(folder_paths) -> Path:
    """The first custom_nodes folder ComfyUI reports (`/internal/folder_paths`) that is on this computer and is a
    custom_nodes folder in a ComfyUI folder; nothing is ever written anywhere else."""
    paths = folder_paths.get('custom_nodes') if isinstance(folder_paths, dict) else None
    found = [Path(path) for path in paths or [] if isinstance(path, str) and Path(path).is_dir()]
    for path in found:
        if comfyui_nodes_folder(path):
            return path
    if found:
        raise DomainError("The folder ComfyUI named for its nodes doesn't look like ComfyUI's custom_nodes folder, "
                          'so nothing was installed. Get the nodes from their page instead, then restart ComfyUI.', 409)
    raise DomainError("ComfyUI didn't say where its custom_nodes folder is. Get the nodes from their page "
                      'instead, then restart ComfyUI.', 409)


async def fetch(pack: dict, transport=None) -> dict[str, bytes]:
    """Every file of the pack, each checked against its pinned hash; nothing is kept on a mismatch."""
    files = {}
    async with httpx.AsyncClient(transport=transport, timeout=60, follow_redirects=False) as client:
        for name, digest in pack['files'].items():
            try:
                response = await client.get(pack['source'] + name)
            except httpx.RequestError as error:
                raise DomainError(f"The {pack['label']} nodes couldn't be downloaded. Check the internet "
                                  'connection and try again.', 502) from error
            if response.status_code != 200 or hashlib.sha256(response.content).hexdigest() != digest:
                raise DomainError(f"The {pack['label']} download didn't match the expected files, so nothing "
                                  'was installed.', 502)
            files[name] = response.content
    return files


def place(folder: Path, pack: dict, files: dict[str, bytes]) -> Path:
    """Write the files into a hidden folder beside the target, then move it into place in one step."""
    target = folder / pack['folder']
    if target.exists():
        raise DomainError(f"{pack['label']} is already in ComfyUI's custom_nodes folder. Restart ComfyUI if "
                          'Check still says its nodes are missing.', 409)
    staging = folder / f".prospero-{pack['folder']}-{uuid.uuid4().hex[:8]}"
    try:
        staging.mkdir()
        for name, content in files.items():
            (staging / name).write_bytes(content)
        staging.rename(target)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return target


async def install(pack_id: str, folder_paths, transport=None) -> Path:
    pack = PACKS.get(pack_id)
    if pack is None:
        raise DomainError('That node pack is not one the app installs.', 404)
    folder = custom_nodes_folder(folder_paths)
    return place(folder, pack, await fetch(pack, transport))
