"""Child processes on a loop without subprocess support: uvicorn's Windows loop under --reload (dev.bat)."""
import asyncio
import sys

import pytest

from dungeon import subprocesses
from dungeon.providers import claude_code
from dungeon.providers.chat import ChatProvider


class NoSubprocessLoop(asyncio.SelectorEventLoop):
    """Fails to start child processes the way a Windows SelectorEventLoop does."""
    async def _make_subprocess_transport(self, *args, **kwargs):
        raise NotImplementedError


# On Windows the real thing; elsewhere a loop that fails the same way.
WITHOUT_SUBPROCESSES = asyncio.SelectorEventLoop if sys.platform == 'win32' else NoSubprocessLoop
ECHO = 'import sys\nfor line in sys.stdin:\n    print(line.strip().upper(), flush=True)\nprint("done")'


def run(main):
    return asyncio.run(main(), loop_factory=WITHOUT_SUBPROCESSES)


def test_this_loop_cannot_start_processes_by_itself():
    async def main():
        await asyncio.create_subprocess_exec(sys.executable, '-c', 'pass')
    with pytest.raises(NotImplementedError):
        run(main)


def test_lines_stream_both_ways_without_subprocess_support():
    async def main():
        process = await subprocesses.start(sys.executable, '-c', ECHO, stdin=asyncio.subprocess.PIPE,
                                           stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
        process.stdin.write(b'one\n')
        await process.stdin.drain()
        first = await process.stdout.readline()
        process.stdin.write(b'two\n')
        process.stdin.close()
        rest = [line async for line in process.stdout]
        return first, rest, await process.wait()
    first, rest, code = run(main)
    assert first.strip() == b'ONE'
    assert [line.strip() for line in rest] == [b'TWO', b'done']
    assert code == 0


def test_communicate_returns_output_and_exit_code():
    async def main():
        process = await subprocesses.start(
            sys.executable, '-c', 'import sys; data = sys.stdin.read(); print(data[::-1]); '
            'print("oops", file=sys.stderr); sys.exit(3)',
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, stderr = await process.communicate(b'abc')
        return stdout, stderr, process.returncode
    stdout, stderr, code = run(main)
    assert stdout.strip() == b'cba'
    assert stderr.strip() == b'oops'
    assert code == 3


def test_a_stuck_process_can_be_timed_out_and_killed():
    async def main():
        process = await subprocesses.start(sys.executable, '-c', 'import time; time.sleep(60)',
                                           stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(process.wait(), 0.2)
        assert process.returncode is None
        process.kill()
        await process.wait()
        return process.returncode
    assert run(main) is not None


def test_a_capable_loop_keeps_asyncio_processes():
    async def main():
        process = await subprocesses.start(sys.executable, '-c', 'pass')
        await process.wait()
        return process
    assert isinstance(asyncio.run(main()), asyncio.subprocess.Process)


def test_the_claude_login_check_runs_without_subprocess_support(tmp_path, monkeypatch):
    stand_in = tmp_path / 'claude_auth.py'
    stand_in.write_text('import json; print(json.dumps({"loggedIn": True, "authMethod": "claude.ai", '
                        '"email": "player@example.com"}))', encoding='utf-8')
    original = subprocesses.start

    async def start(executable, *arguments, **options):
        return await original(executable, str(stand_in), *arguments, **options)
    monkeypatch.setattr(subprocesses, 'start', start)

    async def main():
        return await claude_code.login_state(sys.executable)
    assert run(main) == {'method': 'claude.ai', 'email': 'player@example.com'}


def test_a_cli_that_cannot_start_gets_a_readable_error_not_a_500(client, monkeypatch):
    async def broken(*_args, **_kwargs):
        raise NotImplementedError
    monkeypatch.setattr(claude_code.ClaudeCodeProvider, 'check', broken)
    monkeypatch.setattr(client.app.state, 'provider', ChatProvider())
    response = client.post('/api/models/discover', json={'config': {'provider': 'claude_code', 'model': 'sonnet'}})
    assert response.status_code == 502
    assert 'Claude Code CLI could not be started' in response.text
