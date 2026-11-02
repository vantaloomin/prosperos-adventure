"""Child processes that start on any event loop.

asyncio.create_subprocess_exec needs a loop that supports subprocesses. On Windows uvicorn runs a
SelectorEventLoop whenever it reloads or runs workers (dev.bat's --reload, `uvicorn --reload` by hand), and
that loop raises NotImplementedError for every child process: the Claude Code and Codex logins, replies and
images all failed there. `start` uses asyncio's own process when the loop can make one, and otherwise runs the
same program with subprocess.Popen and threads behind the small part of asyncio's Process the app uses
(stdin write/drain/close, stdout lines, communicate, wait, kill, returncode).
"""
import asyncio
import subprocess
import threading

CHUNK = 65536


async def start(*args, limit: int = 2 ** 16, **options):
    """asyncio.create_subprocess_exec, or the threaded stand-in when this loop cannot start processes."""
    try:
        return await asyncio.create_subprocess_exec(*args, limit=limit, **options)
    except NotImplementedError:
        return ThreadedProcess(args, limit, options)


class ThreadedWriter:
    def __init__(self, pipe):
        self.pipe = pipe
        self.pending = bytearray()

    def write(self, data: bytes):
        self.pending.extend(data)

    async def drain(self):
        data, self.pending = bytes(self.pending), bytearray()
        if data:
            await asyncio.to_thread(self._send, data)

    def _send(self, data: bytes):
        self.pipe.write(data)
        self.pipe.flush()

    def close(self):
        """Flushes what was written without a drain, then closes, so the program sees the end of its input."""
        try:
            if self.pending:
                self._send(bytes(self.pending))
            self.pipe.close()
        except OSError:
            pass
        self.pending = bytearray()


class ThreadedProcess:
    def __init__(self, args, limit: int, options: dict):
        self.popen = subprocess.Popen(list(args), **options)
        self.loop = asyncio.get_running_loop()
        self.stdin = ThreadedWriter(self.popen.stdin) if self.popen.stdin else None
        self.stdout = self._reader(self.popen.stdout, limit)
        self.stderr = self._reader(self.popen.stderr, limit)

    @property
    def pid(self) -> int:
        return self.popen.pid

    @property
    def returncode(self) -> int | None:
        return self.popen.poll()

    def _reader(self, pipe, limit: int):
        if pipe is None:
            return None
        reader = asyncio.StreamReader(limit=limit, loop=self.loop)

        def pump():
            try:
                while data := pipe.read1(CHUNK) if hasattr(pipe, 'read1') else pipe.read(CHUNK):
                    self.loop.call_soon_threadsafe(reader.feed_data, data)
            except (OSError, ValueError):
                pass
            finally:
                try:
                    self.loop.call_soon_threadsafe(reader.feed_eof)
                except RuntimeError:  # the loop closed first
                    pass
        threading.Thread(target=pump, daemon=True).start()
        return reader

    async def wait(self) -> int:
        return await asyncio.to_thread(self.popen.wait)

    async def communicate(self, input: bytes | None = None) -> tuple[bytes | None, bytes | None]:
        if self.stdin is not None:
            if input:
                self.stdin.write(input)
            await asyncio.to_thread(self.stdin.close)
        stdout, stderr = await asyncio.gather(*(stream.read() if stream else asyncio.sleep(0)
                                                for stream in (self.stdout, self.stderr)))
        await self.wait()
        return stdout, stderr

    def kill(self):
        if self.popen.poll() is None:
            self.popen.kill()

    def terminate(self):
        if self.popen.poll() is None:
            self.popen.terminate()
