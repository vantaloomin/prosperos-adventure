"""One-press install of a listed ComfyUI node pack (images/node_packs.py), against stand-ins only."""
import asyncio
import hashlib

import httpx
import pytest

from dungeon.errors import DomainError
from dungeon.images import node_packs

PACK = {'label': 'Test Pack', 'folder': 'comfyui-test', 'source': 'https://example.test/pin/',
        'nodes': ('TestNode',), 'files': {'__init__.py': hashlib.sha256(b'NODES = 1\n').hexdigest(),
                                          'LICENSE': hashlib.sha256(b'Apache\n').hexdigest()}}
FILES = {'/pin/__init__.py': b'NODES = 1\n', '/pin/LICENSE': b'Apache\n'}


@pytest.fixture
def pack(monkeypatch):
    monkeypatch.setitem(node_packs.PACKS, 'test', PACK)
    return PACK


@pytest.fixture
def nodes(tmp_path):
    """A ComfyUI folder's custom_nodes folder, beside its main.py."""
    (tmp_path / 'ComfyUI' / 'custom_nodes').mkdir(parents=True)
    (tmp_path / 'ComfyUI' / 'main.py').write_text('')
    return tmp_path / 'ComfyUI' / 'custom_nodes'


def serve(files):
    return httpx.MockTransport(lambda request: httpx.Response(200, content=files[request.url.path])
                               if request.url.path in files else httpx.Response(404))


def test_installs_a_pinned_pack_as_a_new_folder(pack, nodes):
    target = asyncio.run(node_packs.install('test', {'custom_nodes': [str(nodes)]}, serve(FILES)))
    assert target == nodes / 'comfyui-test'
    assert (target / '__init__.py').read_bytes() == b'NODES = 1\n' and (target / 'LICENSE').exists()
    assert [path.name for path in nodes.iterdir()] == ['comfyui-test']


def test_a_changed_file_installs_nothing(pack, nodes):
    with pytest.raises(DomainError) as error:
        asyncio.run(node_packs.install('test', {'custom_nodes': [str(nodes)]},
                                       serve({**FILES, '/pin/LICENSE': b'something else\n'})))
    assert "didn't match" in error.value.message and list(nodes.iterdir()) == []


def test_an_existing_folder_is_never_replaced(pack, nodes):
    (nodes / 'comfyui-test').mkdir()
    (nodes / 'comfyui-test' / 'mine.py').write_text('kept')
    with pytest.raises(DomainError) as error:
        asyncio.run(node_packs.install('test', {'custom_nodes': [str(nodes)]}, serve(FILES)))
    assert 'already' in error.value.message
    assert [path.name for path in (nodes / 'comfyui-test').iterdir()] == ['mine.py']


def test_needs_a_custom_nodes_folder_on_this_computer(pack, tmp_path):
    for folders in ({}, {'custom_nodes': [str(tmp_path / 'not-here')]}, []):
        with pytest.raises(DomainError):
            asyncio.run(node_packs.install('test', folders, serve(FILES)))
    with pytest.raises(DomainError):
        asyncio.run(node_packs.install('unknown', {'custom_nodes': [str(tmp_path)]}, serve(FILES)))


def test_only_a_custom_nodes_folder_inside_comfyui_takes_a_pack(pack, tmp_path):
    """Whatever folder the server names, nothing is written outside a ComfyUI folder's custom_nodes."""
    elsewhere, bare = tmp_path / 'Documents', tmp_path / 'loose' / 'custom_nodes'
    elsewhere.mkdir()
    bare.mkdir(parents=True)
    for folder in (elsewhere, bare):
        with pytest.raises(DomainError) as error:
            asyncio.run(node_packs.install('test', {'custom_nodes': [str(folder)]}, serve(FILES)))
        assert "doesn't look like ComfyUI's custom_nodes folder" in error.value.message
        assert list(folder.iterdir()) == []
    # The desktop app's folder has models/ beside custom_nodes, and a listed folder that qualifies is the one used.
    desktop = tmp_path / 'desktop' / 'custom_nodes'
    desktop.mkdir(parents=True)
    (tmp_path / 'desktop' / 'models').mkdir()
    target = asyncio.run(node_packs.install('test', {'custom_nodes': [str(elsewhere), str(desktop)]}, serve(FILES)))
    assert target == desktop / 'comfyui-test' and list(elsewhere.iterdir()) == []


def test_the_listed_pack_covers_the_reference_workflows_nodes():
    assert node_packs.providing(['Krea2EditModelPatch', 'KSampler']) == [{'id': 'krea2edit', 'label': 'Krea 2 Identity Edit'}]
    assert node_packs.providing(['KSampler']) == []
    pack = node_packs.PACKS['krea2edit']
    assert '/86f886dac23013d88996e3a2e99093ba44d322fb/' in pack['source'] and '__init__.py' in pack['files']
