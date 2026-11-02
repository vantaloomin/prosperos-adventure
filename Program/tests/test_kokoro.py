"""The built-in voice keeps its own onnxruntime on Windows 11 and offers a repair (dungeon/voice/kokoro.py).

Ported from Prospero's Companion #395. Dungeon does not read voice notes yet; the engine is kept for NPC voices.
"""
import hashlib
import io
import tarfile
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from dungeon.voice import kokoro


def archive(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode='w:bz2') as bundle:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size, info.mode = len(data), 0o755
            bundle.addfile(info, io.BytesIO(data))
    return buffer.getvalue()

def test_the_built_in_voice_puts_its_own_onnxruntime_back_beside_the_program(tmp_path):
    """Without its own onnxruntime.dll beside it, Windows would load Windows 11's older copy from System32."""
    program = tmp_path / 'bin' / kokoro.program_name()
    program.parent.mkdir()
    program.write_bytes(b'program')
    (tmp_path / 'lib').mkdir()
    (tmp_path / 'lib' / 'onnxruntime.dll').write_bytes(b'own runtime')
    (program.parent / 'onnxruntime_providers_shared.dll').write_bytes(b'cut short')
    (tmp_path / 'lib' / 'onnxruntime_providers_shared.dll').write_bytes(b'whole providers')
    kokoro.place_libraries(program)
    assert (program.parent / 'onnxruntime.dll').read_bytes() == b'own runtime'
    assert (program.parent / 'onnxruntime_providers_shared.dll').read_bytes() == b'whole providers'


def test_the_built_in_voice_runs_from_its_own_folder(tmp_path, monkeypatch):
    seen = {}
    monkeypatch.setattr(kokoro.subprocess, 'run', lambda arguments, **options: seen.update(options))
    program = tmp_path / 'sherpa' / 'bin' / kokoro.program_name()
    kokoro.run([str(program), '--sid=3'])
    assert seen['cwd'] == program.parent
    assert seen['env']['PATH'].split(kokoro.os.pathsep)[:2] == [str(program.parent), str(tmp_path / 'sherpa' / 'lib')]


def test_someone_elses_onnxruntime_asks_for_a_repair_that_keeps_the_model(tmp_path, monkeypatch):
    import asyncio
    monkeypatch.delenv(kokoro.PROGRAM_ENV, raising=False)
    monkeypatch.delenv(kokoro.MODEL_ENV, raising=False)
    runtime = archive({f'sherpa/bin/{kokoro.program_name()}': b'program', 'sherpa/lib/onnxruntime.dll': b'own'})
    monkeypatch.setattr(kokoro, 'platform_key', lambda: 'test')
    monkeypatch.setitem(kokoro.RUNTIMES, 'test', ('v1/runtime.tar.bz2', len(runtime), hashlib.sha256(runtime).hexdigest()))
    downloads = []
    transport = httpx.MockTransport(lambda request: downloads.append(request.url.path) or httpx.Response(200, content=runtime))
    model = tmp_path / kokoro.MODEL_NAME
    (model / 'espeak-ng-data').mkdir(parents=True)
    for name in ('model.onnx', 'voices.bin', 'tokens.txt'):
        (model / name).write_bytes(b'x')
    mismatch = (b'The requested API version [28] is not available, only API versions [1, 17] are supported in this '
                b'build. Current ORT Version is: 1.17.1')
    voice = kokoro.Kokoro(tmp_path, transport, lambda _arguments: SimpleNamespace(returncode=1, stderr=mismatch))
    asyncio.run(voice.install())
    assert (Path(voice.program()).parent / 'onnxruntime.dll').exists() is False
    with pytest.raises(Exception, match='older copy of onnxruntime'):
        asyncio.run(voice.speak('Hello', '3', tmp_path / 'note.wav'))
    assert (Path(voice.program()).parent / 'onnxruntime.dll').read_bytes() == b'own'
    status = voice.status()
    assert status['repair'] and not status['ready'] and 'Repair the built-in voice' in status['error']
    status = asyncio.run(voice.repair())
    assert status['ready'] and not status['repair'] and len(downloads) == 2
    assert (model / 'model.onnx').exists()
