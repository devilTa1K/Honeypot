import json, time
from fastapi.testclient import TestClient
from app import analyst_worker, db, geo
from app.main import app

class City:
    def __init__(s, lat, lon, cc): s.location = type("L", (), dict(latitude=lat, longitude=lon))(); s.country = type("C", (), dict(iso_code=cc))()
class Reader:
    def city(self, ip): return City(52.5, 13.4, "DE")

def test_geo_only_locates_public_ips():
    assert geo.locate("10.0.0.5", Reader()) is None and geo.locate("203.0.113.9", Reader()) is None and geo.locate("nonsense", Reader()) is None
    assert geo.locate("8.8.8.8", Reader())["country"] == "DE"

def test_geo_summary_and_endpoint_without_database():
    evs = [{"ip": "8.8.8.8"}, {"ip": "8.8.8.8"}, {"ip": "10.1.1.1"}]
    s = geo.summarize(evs, Reader())
    assert s["geoip_enabled"] and s["points"][0]["count"] == 2 and s["unlocated_ips"] == 1
    j = TestClient(app).get("/admin/geo").json()
    assert j["geoip_enabled"] is False and j["points"] == []

class Fake:
    def complete(self, system, user): return json.dumps({"summary": "LLM view of probing.", "risk": "low", "confidence": 0.7, "recommendations": ["Rate-limit"]})

def _ev(t, sid="bbbbbbbbbbbb"): return dict(ts=t, session=sid, ip="203.0.113.5", method="GET", path="/.env", ua="u", body="", label="data_discovery_attempt")

def test_worker_stores_llm_investigation_and_app_serves_it():
    db.insert_event(_ev(time.time() - 600)); c = TestClient(app)
    assert c.get("/admin/analyze/bbbbbbbbbbbb").json()["source"] == "deterministic"      # app process never calls the LLM
    assert analyst_worker.run_once(Fake()) == 1 and analyst_worker.run_once(Fake()) == 0   # idempotent
    assert c.get("/admin/analyze/bbbbbbbbbbbb").json()["source"] == "llm"
    db.insert_event(_ev(time.time() - 500))                                              # new activity: stored result is stale
    assert c.get("/admin/analyze/bbbbbbbbbbbb").json()["source"] == "deterministic"
    assert analyst_worker.run_once(Fake()) == 1

def test_worker_skips_active_sessions():
    db.insert_event(_ev(time.time())); assert analyst_worker.run_once(Fake()) == 0
