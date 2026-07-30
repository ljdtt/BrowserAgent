# -*- coding: utf-8 -*-
"""
Python 3.13 Windows asyncio.create_subprocess_exec ??
????? Playwright ?????? streamlit_app.py ??? import?
"""

import asyncio
import subprocess as _sp


class _PWrap:
    def __init__(self, proc, loop):
        self._proc = proc
        self._stdout = _PReader(proc.stdout, loop) if proc.stdout else None
        self._stderr = _PReader(proc.stderr, loop) if proc.stderr else None
        self._stdin = _PWriter(proc.stdin, loop) if proc.stdin else None
    @property
    def pid(self): return self._proc.pid
    @property
    def returncode(self): return self._proc.returncode
    @property
    def stdin(self): return self._stdin
    @property
    def stdout(self): return self._stdout
    @property
    def stderr(self): return self._stderr
    async def wait(self):
        return await asyncio.get_running_loop().run_in_executor(None, self._proc.wait)
    async def communicate(self, input=None):
        return await asyncio.get_running_loop().run_in_executor(None, self._proc.communicate, input)
    def send_signal(self, sig): self._proc.send_signal(sig)
    def terminate(self): self._proc.terminate()
    def kill(self): self._proc.kill()


class _PReader:
    def __init__(self, stream, loop):
        self._stream, self._loop = stream, loop
    async def readexactly(self, n):
        data = b""
        while len(data) < n:
            chunk = await self._loop.run_in_executor(None, self._stream.read, n - len(data))
            if not chunk: raise asyncio.IncompleteReadError(data, n)
            data += chunk
        return data
    async def read(self, n=-1):
        return await self._loop.run_in_executor(None, self._stream.read, n if n >= 0 else -1)
    def close(self): self._stream.close()


class _PWriter:
    def __init__(self, stream, loop):
        self._stream = stream
        self._loop = loop
    def write(self, data):
        self._stream.write(data)
    async def drain(self):
        pass
    def close(self):
        self._stream.close()


_original = asyncio.create_subprocess_exec

async def _patched(program, *args, **kwargs):
    pk = {k: v for k, v in kwargs.items() if k not in ("limit", "loop", "start_new_session")}
    proc = _sp.Popen([program, *args], **pk)
    return _PWrap(proc, asyncio.get_running_loop())

# Apply patch at BOTH levels
asyncio.create_subprocess_exec = _patched
try:
    import asyncio.subprocess
    asyncio.subprocess.create_subprocess_exec = _patched
except Exception:
    pass
