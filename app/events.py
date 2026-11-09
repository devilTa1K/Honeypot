import ipaddress
from typing import Awaitable, Callable
from fastapi import Request
from starlette.concurrency import run_in_threadpool
from . import bus, db, log, runtime
from .netutil import trusted

listeners: list[Callable[[dict], Awaitable[None]]] = []   # in-process delivery (dev/combined mode, or Redis outage)

def client_ip(request: Request) -> str:
    """Use X-Forwarded-For only when the direct peer is a trusted proxy (prevents spoofing)."""
    peer = request.client.host if request.client else "?"
    xff = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    try:
        if xff and trusted(peer): return str(ipaddress.ip_address(xff))
    except ValueError:
        pass
    return peer

_log = log.get('events')

async def emit(ev: dict) -> None:
    ev.setdefault("env", runtime.env_name())
    await run_in_threadpool(db.insert_event, ev)
    _log.info("event", extra={"fields": {k: str(ev[k])[:120] for k in ("session", "ip", "method", "path", "label", "env")}})   # no bodies or passwords
    try:
        if bus.redis_client():
            await bus.publish(ev); return
    except Exception:
        pass
    for fn in list(listeners): await fn(ev)
