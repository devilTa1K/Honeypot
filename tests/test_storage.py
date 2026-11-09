import os, time, pytest
from sqlalchemy import inspect
from fastapi.testclient import TestClient
from app import bus, db
from app.main import app

def ev(**k): return {**dict(ts=time.time(), session="aaaaaaaaaaaa", ip="203.0.113.5", method="GET", path="/x", ua="u", body="", label="reconnaissance"), **k}

def test_migrations_create_schema():
    insp = inspect(db.engine())
    assert {"events", "investigations", "environments", "alembic_version"} <= set(insp.get_table_names())
    assert {c["name"] for c in insp.get_columns("events")} == {"id", "ts", "session", "ip", "method", "path", "ua", "body", "label", "env"}

def test_hostile_values_do_not_break_storage():
    db.insert_event(ev(path="/a\x00b", method="FOOBARBAZQUUXFOOBARBAZ", body="B" * 9000, ua="U" * 9000))
    r = db.recent_events(1)[0]
    assert "\x00" not in r["path"] and len(r["method"]) == 16 and len(r["body"]) == 2000

def test_retention_purge():
    db.insert_event(ev(ts=time.time() - 40 * 86400)); db.insert_event(ev())
    assert db.purge_older_than(30) == 1 and len(db.recent_events()) == 1

def test_rate_limit_caps_stored_events(monkeypatch):
    monkeypatch.setenv("HIAB_RATE_PER_MIN", "3")
    c = TestClient(app); c.post("/admin/company", params={"name": "Rl"})
    for _ in range(6): assert c.get("/wiki").status_code == 200   # still answered
    assert len(c.get("/admin/events").json()) == 3

def test_attacker_cannot_choose_session_id():
    c = TestClient(app); c.post("/admin/company", params={"name": "Sid"})
    c.get("/wiki", cookies={"sid": "x" * 500})
    assert len(db.recent_events(1)[0]["session"]) == 12

@pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"), reason="needs TEST_DATABASE_URL (PostgreSQL)")
def test_postgres_migrations_and_hostile_values(monkeypatch):
    url = os.environ["TEST_DATABASE_URL"]; monkeypatch.setenv("DATABASE_URL", url)
    from sqlalchemy import create_engine, text
    with create_engine(url).begin() as c:
        for t in ("events", "investigations", "settings", "audit", "environments", "alembic_version"): c.execute(text(f"DROP TABLE IF EXISTS {t}"))
    assert {"events", "investigations"} <= set(inspect(db.engine()).get_table_names())
    db.insert_event(ev(path="/a\x00b", method="FOOBARBAZQUUXFOOBARBAZ"))
    assert db.recent_events(1)[0]["path"] == "/a\\x00b"

@pytest.mark.skipif(not os.environ.get("REDIS_URL_TEST"), reason="needs REDIS_URL_TEST")
def test_redis_pubsub_and_rate_limit(monkeypatch):
    import asyncio
    monkeypatch.setenv("REDIS_URL", os.environ["REDIS_URL_TEST"]); monkeypatch.setenv("HIAB_RATE_PER_MIN", "2")
    async def main():
        bus.reset(); got = []
        async def reader():
            async for e in bus.listen(): got.append(e); return
        t = asyncio.create_task(reader()); await asyncio.sleep(0.3)
        await bus.publish(ev(path="/via-redis")); await asyncio.wait_for(t, 5)
        r = bus.redis_client(); await r.delete("hiab:rl:9.9.9.9")
        res = [await bus.allow("9.9.9.9") for _ in range(3)]
        await r.delete("hiab:rl:9.9.9.9"); await r.aclose()
        return got, res
    got, res = asyncio.run(main())
    assert got[0]["path"] == "/via-redis" and res == [True, True, False]
