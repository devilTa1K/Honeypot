"""SSH honeypot: records auth attempts and commands; the shell is simulated (see shell.py). Port forwarding, SFTP and SCP are off."""
import asyncio, ipaddress, time, uuid
from typing import Awaitable, Callable
import asyncssh
from .classifier import classify_command
from .netutil import trusted
from .shell import FakeShell

ACCEPT_AFTER = 3          # accept the Nth password attempt from the same IP (lets researchers in)
MAX_SESSIONS, MAX_CMDS, MAX_LINE, SESSION_SECS, IDLE_SECS = 20, 200, 256, 300, 60
Emit = Callable[[dict], Awaitable[None]]
_attempts: dict[str, int] = {}
_active = {"n": 0}
_real_ip: dict[int, str] = {}   # loopback bridge source port -> real client IP (PROXY protocol)

def reset_state() -> None:
    _attempts.clear(); _active["n"] = 0

def _ev(sid: str, ip: str, method: str, path: str, body: str, label: str) -> dict:
    return dict(ts=time.time(), session=sid, ip=ip, method=method, path=path[:MAX_LINE], ua="ssh", body=body[:200], label=label)

class Pot(asyncssh.SSHServer):
    def __init__(self, emit: Emit, is_open: Callable[[], bool]):
        self.emit, self.is_open, self.sid, self.ip = emit, is_open, uuid.uuid4().hex[:12], "?"
    def connection_made(self, conn):
        self.conn, self.peer = conn, (conn.get_extra_info("peername") or ("?", 0))[:2]
        conn.set_extra_info(hiab_sid=self.sid)
        _active["n"] += 1
        if _active["n"] > MAX_SESSIONS: conn.abort()
    def connection_lost(self, exc): _active["n"] = max(0, _active["n"] - 1)
    def begin_auth(self, username): return True
    def password_auth_supported(self): return True
    async def validate_password(self, username, password):
        if not self.is_open(): return False
        h, p = self.peer
        self.ip = _real_ip.get(p, h) if h == "127.0.0.1" else h
        self.conn.set_extra_info(hiab_ip=self.ip)
        if len(_attempts) > 10000: _attempts.clear()
        _attempts[self.ip] = n = _attempts.get(self.ip, 0) + 1
        ok = n >= ACCEPT_AFTER
        await self.emit(_ev(self.sid, self.ip, "SSH-AUTH", username, f"password={password[:64]} accepted={ok}", "credential_probing"))
        return ok

def _handler(emit: Emit, is_open: Callable[[], bool]):
    async def handle(proc: asyncssh.SSHServerProcess):
        sid, ip = proc.get_extra_info("hiab_sid"), proc.get_extra_info("hiab_ip") or "?"
        sh, n, end = FakeShell(), 0, time.time() + SESSION_SECS
        async def run(line: str) -> bool:
            await emit(_ev(sid, ip, "SSH", line, "", classify_command(line)))
            out, quit_ = sh.run(line); proc.stdout.write(out); return quit_
        try:
            if proc.command:
                await run(proc.command[:MAX_LINE]); return
            proc.stdout.write("Welcome to Ubuntu 22.04.3 LTS (GNU/Linux 5.15.0-91-generic x86_64)\n" + sh.prompt())
            while n < MAX_CMDS and time.time() < end and is_open():
                line = (await asyncio.wait_for(proc.stdin.readline(), IDLE_SECS)).strip()[:MAX_LINE]
                if not line:
                    if proc.stdin.at_eof(): break
                    proc.stdout.write(sh.prompt()); continue
                n += 1
                if await run(line): break
                proc.stdout.write(sh.prompt())
        except (asyncio.TimeoutError, asyncssh.Error, ConnectionError):
            pass
        finally:
            proc.exit(0)
    return handle

async def _pipe(r: asyncio.StreamReader, w: asyncio.StreamWriter) -> None:
    try:
        while data := await r.read(65536):
            w.write(data); await w.drain()
    except Exception:
        pass
    finally:
        w.close()

class Front:
    """TCP front that reads a PROXY protocol v1 line (from a trusted proxy only) and bridges to the SSH server on loopback."""
    def __init__(self, front, inner): self.front, self.inner = front, inner
    def get_port(self) -> int: return self.front.sockets[0].getsockname()[1]
    def close(self) -> None: self.front.close(); self.inner.close()
    async def wait_closed(self) -> None: await self.front.wait_closed(); await self.inner.wait_closed()

async def start_ssh(emit: Emit, is_open: Callable[[], bool], host: str = "0.0.0.0", port: int = 2222, proxy_protocol: bool = False):
    key = [asyncssh.generate_private_key("ssh-ed25519")]
    kw = dict(process_factory=_handler(emit, is_open), server_host_keys=key, login_timeout=30, server_version="OpenSSH_8.9p1 Ubuntu-3ubuntu0.6")
    if not proxy_protocol:
        return await asyncssh.create_server(lambda: Pot(emit, is_open), host, port, **kw)
    inner = await asyncssh.create_server(lambda: Pot(emit, is_open), "127.0.0.1", 0, **kw)
    inner_port = inner.get_port()
    async def on_conn(r: asyncio.StreamReader, w: asyncio.StreamWriter) -> None:
        local = None
        try:
            if not trusted(w.get_extra_info("peername")[0]): raise ValueError("untrusted peer")
            parts = (await asyncio.wait_for(r.readuntil(b"\r\n"), 5)).decode("ascii").split()
            if len(parts) < 6 or parts[0] != "PROXY": raise ValueError("bad PROXY header")
            real = str(ipaddress.ip_address(parts[2]))
            ir, iw = await asyncio.open_connection("127.0.0.1", inner_port)
            local = iw.get_extra_info("sockname")[1]; _real_ip[local] = real
        except Exception:
            w.close(); return
        try:
            await asyncio.gather(_pipe(r, iw), _pipe(ir, w))
        finally:
            _real_ip.pop(local, None)
    front = await asyncio.start_server(on_conn, host, port, limit=256)
    return Front(front, inner)
