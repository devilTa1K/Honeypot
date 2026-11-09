import os, tempfile
os.environ["HIAB_DB"] = tempfile.mktemp(suffix=".db")
from fastapi.testclient import TestClient
from app.main import app
from app.classifier import classify
from app.generator import generate_company

def test_generator_deterministic_and_fake():
    a, b = generate_company("Acme Pay", "Fintech", 20), generate_company("Acme Pay", "Fintech", 20)
    assert a == b and a.domain.endswith(".example") and len(a.employees) == 20

def test_classifier_labels_attempts():
    assert classify("/login") == "credential_probing"
    assert classify("/x?a=../../etc/passwd") == "exploitation_attempt"
    assert classify("/.env") == "data_discovery_attempt"

def test_flow_capture_report_and_killswitch():
    c = TestClient(app)
    assert c.get("/directory").status_code == 503
    c.post("/admin/company", params={"name": "Acme Pay"})
    c.get("/robots.txt"); c.get("/directory"); c.post("/login", json={"u": "admin", "p": "x"}); c.get("/.env")
    ev = c.get("/admin/events").json()
    assert len(ev) >= 4
    r = c.get(f"/admin/report/{ev[0]['session']}").json()
    assert r["events"] >= 1 and "credential_probing" in r["stages_observed"]
    c.post("/admin/kill")
    assert c.get("/wiki").status_code == 503
    assert any("EMERGENCY" in a["action"] for a in c.get("/admin/audit").json())

def test_admin_auth_and_replay(monkeypatch):
    monkeypatch.setenv("HIAB_ADMIN_TOKEN", "s3cret")
    c = TestClient(app); h = {"x-admin-token": "s3cret"}
    assert c.get("/admin/events").status_code == 401
    assert c.post("/admin/company", params={"name": "Beta Corp"}, headers=h).status_code == 200
    c.get("/wiki"); c.get("/.env")
    sid = c.get("/admin/events", headers=h).json()[0]["session"]
    rp = c.get(f"/admin/replay/{sid}", headers=h).json()
    assert [e["path"] for e in rp][-2:] == ["/wiki", "/.env"] and rp[0]["t"] == 0
    assert c.get("/healthz").json() == {"ok": True}

def test_websocket_requires_token(monkeypatch):
    import pytest
    from starlette.websockets import WebSocketDisconnect
    monkeypatch.setenv("HIAB_ADMIN_TOKEN", "s3cret")
    c = TestClient(app)
    with pytest.raises(WebSocketDisconnect):
        with c.websocket_connect("/ws"): pass
    with c.websocket_connect("/ws?token=s3cret") as w: w.send_text("ping")

def test_real_ip_only_from_trusted_proxy(monkeypatch):
    monkeypatch.delenv("HIAB_ADMIN_TOKEN", raising=False)
    h = {"x-forwarded-for": "203.0.113.9"}
    c = TestClient(app, client=("172.25.0.3", 5000)); c.post("/admin/company", params={"name": "Gamma"})
    c.get("/wiki", headers=h)
    assert c.get("/admin/events").json()[0]["ip"] == "203.0.113.9"
    u = TestClient(app, client=("8.8.8.8", 5000)); u.get("/wiki", headers=h)      # untrusted peer: header ignored
    assert u.get("/admin/events").json()[0]["ip"] == "8.8.8.8"
