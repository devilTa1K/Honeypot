"""Storage layer (SQLAlchemy Core). SQLite for dev/tests, PostgreSQL in the Docker stack. Schema is owned by Alembic migrations."""
import os, time
from pathlib import Path
from sqlalchemy import Column, Float, Index, Integer, MetaData, String, Table, Text, create_engine, delete, func, insert, select, update
from sqlalchemy.engine import Engine

metadata = MetaData()
events = Table("events", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True), Column("ts", Float, nullable=False),
    Column("session", String(32), nullable=False), Column("ip", String(64), nullable=False), Column("method", String(16), nullable=False),
    Column("path", Text, nullable=False), Column("ua", Text, nullable=False), Column("body", Text, nullable=False), Column("label", String(40), nullable=False), Column("env", String(64), nullable=False, server_default=""),
    Index("ix_events_session", "session"), Index("ix_events_ts", "ts"),
    implicit_returning=False)  # insert-only DB role has no SELECT, so INSERT ... RETURNING would be denied
investigations = Table("investigations", metadata,
    Column("session", String(32), primary_key=True), Column("n_events", Integer, nullable=False), Column("source", String(16), nullable=False),
    Column("payload", Text, nullable=False), Column("created_at", Float, nullable=False))
settings = Table("settings", metadata, Column("key", String(64), primary_key=True), Column("value", Text, nullable=False))
audit = Table("audit", metadata, Column("id", Integer, primary_key=True, autoincrement=True), Column("ts", Float, nullable=False), Column("action", Text, nullable=False))
environments = Table("environments", metadata,
    Column("id", String(32), primary_key=True), Column("name", String(64), nullable=False), Column("industry", String(64), nullable=False),
    Column("size", Integer, nullable=False), Column("port", Integer), Column("status", String(16), nullable=False, server_default="running"),
    Column("created_at", Float, nullable=False))
_engines: dict[str, Engine] = {}
_LIMITS = {"session": 32, "ip": 64, "method": 16, "label": 40, "path": 2000, "ua": 500, "body": 2000, "env": 64}

def database_url() -> str:
    return os.environ.get("DATABASE_URL") or f"sqlite:///{os.environ.get('HIAB_DB', 'events.db')}"

def migrate(url: str) -> None:
    from alembic import command
    from alembic.config import Config
    cfg = Config()
    cfg.set_main_option("script_location", str(Path(__file__).resolve().parent.parent / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(cfg, "head")

def engine() -> Engine:
    url = database_url()
    if url not in _engines:
        if os.environ.get("HIAB_SKIP_MIGRATE") != "1":
            migrate(url)
        _engines[url] = create_engine(url, pool_pre_ping=True)
    return _engines[url]

def dispose_all() -> None:
    for e in _engines.values(): e.dispose()
    _engines.clear()

def _clean(ev: dict) -> dict:
    """Attacker-controlled strings: drop NUL bytes (PostgreSQL rejects them) and enforce column limits."""
    out = {"ts": ev["ts"]}
    for k, n in _LIMITS.items():
        out[k] = str(ev.get(k, "")).replace("\x00", "\\x00")[:n]
    return out

def insert_event(ev: dict) -> None:
    with engine().begin() as c: c.execute(insert(events), _clean(ev))

def recent_events(limit: int = 200) -> list[dict]:
    with engine().connect() as c:
        return [dict(r._mapping) for r in c.execute(select(events).order_by(events.c.id.desc()).limit(limit))]

def session_events(sid: str) -> list[dict]:
    with engine().connect() as c:
        return [dict(r._mapping) for r in c.execute(select(events).where(events.c.session == sid).order_by(events.c.id))]

def purge_older_than(days: float) -> int:
    engine()  # make sure schema exists
    if days <= 0: return 0
    with engine().begin() as c: return c.execute(delete(events).where(events.c.ts < time.time() - days * 86400)).rowcount

def sessions_needing_analysis(idle_secs: float, limit: int = 20) -> list[tuple[str, int]]:
    """Idle sessions whose stored investigation is missing or covers fewer events than now exist."""
    with engine().connect() as c:
        rows = c.execute(select(events.c.session, func.count().label("n")).group_by(events.c.session)
                         .having(func.max(events.c.ts) < time.time() - idle_secs).order_by(func.max(events.c.ts).desc()).limit(100)).all()
        done = {r.session: r.n_events for r in c.execute(select(investigations.c.session, investigations.c.n_events)
                .where(investigations.c.session.in_([r.session for r in rows])))} if rows else {}
    return [(r.session, r.n) for r in rows if done.get(r.session) != r.n][:limit]

def save_investigation(sid: str, n: int, source: str, payload: str) -> None:
    vals = dict(n_events=n, source=source, payload=payload, created_at=time.time())
    with engine().begin() as c:
        if c.execute(update(investigations).where(investigations.c.session == sid).values(**vals)).rowcount == 0:
            c.execute(insert(investigations).values(session=sid, **vals))

def get_investigation(sid: str) -> dict | None:
    with engine().connect() as c:
        r = c.execute(select(investigations).where(investigations.c.session == sid)).first()
        return dict(r._mapping) if r else None

def set_setting(key: str, value: str) -> None:
    with engine().begin() as c:
        if c.execute(update(settings).where(settings.c.key == key).values(value=value)).rowcount == 0:
            c.execute(insert(settings).values(key=key, value=value))

def get_setting(key: str) -> str | None:
    with engine().connect() as c:
        return c.execute(select(settings.c.value).where(settings.c.key == key)).scalar()

def log_admin(action: str) -> None:
    with engine().begin() as c: c.execute(insert(audit).values(ts=time.time(), action=action[:500]))

def admin_log(limit: int = 200) -> list[dict]:
    with engine().connect() as c:
        rows = c.execute(select(audit.c.ts, audit.c.action).order_by(audit.c.id.desc()).limit(limit)).all()
    return [{"ts": r.ts, "action": r.action} for r in reversed(rows)]

def all_settings() -> dict[str, str]:
    with engine().connect() as c: return {r.key: r.value for r in c.execute(select(settings.c.key, settings.c.value))}

def upsert_environment(slug: str, name: str, industry: str, size: int) -> None:
    vals = dict(name=name, industry=industry, size=size)
    with engine().begin() as c:
        if c.execute(update(environments).where(environments.c.id == slug).values(**vals)).rowcount == 0:
            c.execute(insert(environments).values(id=slug, status="running", created_at=time.time(), **vals))

def get_environment(slug: str) -> dict | None:
    with engine().connect() as c:
        r = c.execute(select(environments).where(environments.c.id == slug)).first()
        return dict(r._mapping) if r else None

def list_environments() -> list[dict]:
    with engine().connect() as c:
        counts = {r.env: r.n for r in c.execute(select(events.c.env, func.count().label("n")).group_by(events.c.env))}
        return [{**dict(r._mapping), "event_count": counts.get(r.id, 0)} for r in c.execute(select(environments).order_by(environments.c.created_at))]

def update_environment(slug: str, **vals) -> bool:
    with engine().begin() as c: return c.execute(update(environments).where(environments.c.id == slug).values(**vals)).rowcount > 0

def delete_environment(slug: str) -> bool:
    with engine().begin() as c: return c.execute(delete(environments).where(environments.c.id == slug)).rowcount > 0

def trim_to(cap: int) -> int:
    """Disk quota: keep at most `cap` newest events."""
    with engine().begin() as c:
        cutoff = c.execute(select(events.c.id).order_by(events.c.id.desc()).offset(cap).limit(1)).scalar()
        return c.execute(delete(events).where(events.c.id <= cutoff)).rowcount if cutoff is not None else 0

def investigation_stats() -> dict:
    with engine().connect() as c: return {r.source: r.n for r in c.execute(select(investigations.c.source, func.count().label("n")).group_by(investigations.c.source))}
