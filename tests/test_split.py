import os, pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from app import control, db, decoy

def test_decoy_has_no_admin_surface_and_control_has_no_decoys():
    ctl, dec = TestClient(control.app), TestClient(decoy.app)
    assert ctl.post("/admin/company", params={"name": "Split"}).status_code == 200
    assert dec.get("/admin/events").status_code == 404 and dec.get("/openapi.json").status_code == 404   # probe is just a 404
    assert dec.get("/wiki").status_code == 200 and ctl.get("/wiki").status_code == 404
    assert {e["path"] for e in ctl.get("/admin/events").json()} == {"/admin/events", "/openapi.json", "/wiki"}               # probes were captured
    assert "Split" in dec.get("/").text

def test_kill_switch_crosses_processes_and_audit_is_persisted():
    ctl, dec = TestClient(control.app), TestClient(decoy.app)
    assert dec.get("/wiki").status_code == 503                    # nothing deployed yet
    ctl.post("/admin/company", params={"name": "Kill"}); assert dec.get("/wiki").status_code == 200
    ctl.post("/admin/kill"); assert dec.get("/wiki").status_code == 503
    ctl.post("/admin/company", params={"name": "Kill"}); assert dec.get("/wiki").status_code == 200
    assert [a["action"] for a in ctl.get("/admin/audit").json()] == ["generate company Kill", "EMERGENCY SHUTDOWN", "generate company Kill"]

@pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"), reason="needs TEST_DATABASE_URL (PostgreSQL superuser)")
def test_postgres_role_separation(monkeypatch):
    base = make_url(os.environ["TEST_DATABASE_URL"]); su = base.render_as_string(hide_password=False)
    for k, v in dict(HIAB_ANALYST_DB_PASSWORD="analystpw99", HIAB_INGEST_DB_PASSWORD="ingestpw99", HIAB_CONTROL_DB_PASSWORD="controlpw99").items(): monkeypatch.setenv(k, v)
    with create_engine(su).begin() as c:
        for t in ("events", "investigations", "settings", "audit", "environments", "alembic_version"): c.execute(text(f"DROP TABLE IF EXISTS {t}"))
    db.migrate(su)
    def as_role(user, pw):
        db.dispose_all(); monkeypatch.setenv("DATABASE_URL", base.set(username=user, password=pw).render_as_string(hide_password=False)); monkeypatch.setenv("HIAB_SKIP_MIGRATE", "1")
    ev = dict(ts=1.0, session="aaaaaaaaaaaa", ip="1.2.3.4", method="GET", path="/x", ua="u", body="", label="reconnaissance")
    def denied(fn):
        try: fn(); return False
        except Exception: return True
    as_role("hiab_control", "controlpw99"); db.set_setting("company", '{"name":"A","industry":"B","size":5}')
    assert denied(lambda: db.insert_event(ev))                         # control plane cannot forge events
    as_role("hiab_ingest", "ingestpw99")
    db.insert_event(ev); assert db.get_setting("company")             # decoy can add events and read settings
    assert denied(db.recent_events) and denied(lambda: db.set_setting("killed", "0")) and denied(lambda: db.log_admin("x"))   # cannot read events or change settings
    assert db.get_environment("nope") is None and denied(lambda: db.upsert_environment("x", "X", "Y", 5))   # decoy reads environments but cannot write them
    as_role("hiab_control", "controlpw99"); db.upsert_environment("x", "X", "Y", 5); assert db.get_environment("x")["name"] == "X"
    assert len(db.recent_events()) == 1 and db.purge_older_than(0.0000001) == 1
