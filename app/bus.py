"""Redis pub/sub for live events (multi-process fan-out) and per-IP rate limiting. Falls back to in-process when REDIS_URL is unset."""
import json, os, time
CHANNEL = "hiab:events"
_redis = None
_hits: dict[str, tuple[float, int]] = {}

def redis_client():
    global _redis
    url = os.environ.get("REDIS_URL")
    if not url: return None
    if _redis is None:
        import redis.asyncio as aioredis
        _redis = aioredis.from_url(url, decode_responses=True)
    return _redis

def reset() -> None:
    global _redis
    _redis = None; _hits.clear()

async def publish(ev: dict) -> None:
    await redis_client().publish(CHANNEL, json.dumps(ev))

async def listen():
    ps = redis_client().pubsub()
    await ps.subscribe(CHANNEL)
    async for m in ps.listen():
        if m["type"] == "message": yield json.loads(m["data"])

async def allow(ip: str, limit: int | None = None) -> bool:
    """Cap stored events per source IP per minute (disk-fill protection). Requests are still answered when over the limit."""
    limit = limit if limit is not None else int(os.environ.get("HIAB_RATE_PER_MIN", "300"))
    r = redis_client()
    if r:
        k = f"hiab:rl:{ip}"; n = await r.incr(k)
        if n == 1: await r.expire(k, 60)
        return n <= limit
    now = time.time(); start, n = _hits.get(ip, (now, 0))
    if now - start >= 60: start, n = now, 0
    if len(_hits) > 10000: _hits.clear()
    _hits[ip] = (start, n + 1)
    return n + 1 <= limit
