"""Operator control plane: admin API, WebSocket live feed, dashboard. Never serves decoy routes; reads events, cannot insert them."""
import asyncio, json, os
from pydantic import BaseModel, Field
from contextlib import asynccontextmanager
from fastapi import APIRouter, FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.concurrency import run_in_threadpool
from . import bus, db, events, geo, intel, log, runtime
from .analyst import analyze
from .generator import generate_company
from .provision import PORT_RANGE, slugify

router = APIRouter()
clients: set[WebSocket] = set()

async def broadcast(ev: dict) -> None:
    for w in list(clients):
        try: await w.send_json(ev)
        except Exception: clients.discard(w)
events.listeners.append(broadcast)

async def _relay() -> None:
    while True:
        try:
            async for ev in bus.listen(): await broadcast(ev)
        except asyncio.CancelledError:
            raise
        except Exception:
            await asyncio.sleep(2)

DEFAULTS = {"rate_per_min": 300, "retention_days": 30, "max_events": 1_000_000}
_audit_log = log.get("admin")

def effective_settings() -> dict[str, int]:
    s = db.all_settings(); env = {"rate_per_min": os.environ.get("HIAB_RATE_PER_MIN"), "retention_days": os.environ.get("HIAB_RETENTION_DAYS")}
    out = {}
    for k, d in DEFAULTS.items():
        try: out[k] = int(s.get(k) or env.get(k) or d)
        except ValueError: out[k] = d
    return out

def maintenance_once() -> dict:
    s = effective_settings()
    return {"purged": db.purge_older_than(float(s["retention_days"])), "trimmed": db.trim_to(s["max_events"])}

async def _maintenance() -> None:
    while True:
        try: await run_in_threadpool(maintenance_once)
        except Exception: _audit_log.exception("maintenance failed")
        await asyncio.sleep(float(os.environ.get("HIAB_MAINT_SECS", "3600")))

def _audit(action: str) -> None:
    db.log_admin(action); _audit_log.info("admin", extra={"fields": {"action": action}})

@asynccontextmanager
async def lifespan(_app):
    tasks = [asyncio.create_task(_maintenance())]
    if bus.redis_client(): tasks.append(asyncio.create_task(_relay()))
    yield
    for t in tasks: t.cancel()

async def admin_auth(request: Request, call_next):
    if request.url.path.startswith("/admin"):
        tok = os.environ.get("HIAB_ADMIN_TOKEN")
        if tok and request.headers.get("x-admin-token") != tok: return JSONResponse({"error": "unauthorized"}, 401)
    return await call_next(request)

def _env_args(name: str, industry: str, size: int):
    return name.strip()[:64], industry.strip()[:64], min(max(size, 5), 200)

@router.post("/admin/company")
def create_company(name: str, industry: str = "Fintech", size: int = 50):
    """Create (or update) an environment and make it the one the global decoy serves."""
    name, industry, size = _env_args(name, industry, size)
    if not name: return JSONResponse({"error": "name required"}, 422)
    slug = slugify(name); c = generate_company(name, industry, size)
    db.upsert_environment(slug, name, industry, size); db.set_setting("active_env", slug); db.set_setting("killed", "0")
    _audit(f"generate company {name}"); runtime.reset()
    return {"domain": c.domain, "employees": len(c.employees), "environment": slug}

@router.post("/admin/kill")
def kill():
    db.set_setting("killed", "1"); _audit("EMERGENCY SHUTDOWN"); runtime.reset(); return {"killed": True}

@router.get("/admin/environments")
def environments():
    active = db.all_settings().get("active_env", "")
    return [{**e, "active": e["id"] == active} for e in db.list_environments()]

@router.post("/admin/environments")
def create_environment(name: str, industry: str = "Fintech", size: int = 50):
    name, industry, size = _env_args(name, industry, size)
    if not name: return JSONResponse({"error": "name required"}, 422)
    db.upsert_environment(slugify(name), name, industry, size); _audit(f"create environment {name}")
    return {"environment": slugify(name)}

@router.post("/admin/environments/{slug}/activate")
def activate(slug: str):
    if not db.get_environment(slug): return JSONResponse({"error": "unknown environment"}, 404)
    db.set_setting("active_env", slug); db.set_setting("killed", "0"); db.update_environment(slug, status="running"); _audit(f"activate environment {slug}"); runtime.reset()
    return {"active": slug}

@router.post("/admin/environments/{slug}/status")
def env_status(slug: str, value: str):
    if value not in ("running", "stopped"): return JSONResponse({"error": "value must be running or stopped"}, 422)
    if not db.update_environment(slug, status=value): return JSONResponse({"error": "unknown environment"}, 404)
    _audit(f"environment {slug} {value}"); runtime.reset(); return {"status": value}

@router.post("/admin/environments/{slug}/port")
def env_port(slug: str, value: int):
    if value not in PORT_RANGE: return JSONResponse({"error": f"port must be in {PORT_RANGE.start}-{PORT_RANGE.stop - 1}"}, 422)
    if any(e["port"] == value and e["id"] != slug for e in db.list_environments()): return JSONResponse({"error": "port in use"}, 409)
    if not db.update_environment(slug, port=value): return JSONResponse({"error": "unknown environment"}, 404)
    _audit(f"environment {slug} port {value}"); return {"port": value}

@router.delete("/admin/environments/{slug}")
def delete_env(slug: str):
    if not db.delete_environment(slug): return JSONResponse({"error": "unknown environment"}, 404)
    if db.all_settings().get("active_env") == slug: db.set_setting("active_env", "")
    _audit(f"delete environment {slug}"); runtime.reset(); return {"deleted": slug}

class SettingsIn(BaseModel):
    rate_per_min: int | None = Field(None, ge=1, le=10000)
    retention_days: int | None = Field(None, ge=0, le=3650)
    max_events: int | None = Field(None, ge=1000, le=10_000_000)

@router.get("/admin/settings")
def get_settings():
    return {"settings": effective_settings(), "defaults": DEFAULTS, "runtime": {"database": db.engine().dialect.name, "redis": bool(bus.redis_client()),
            "geoip": geo.reader() is not None, "investigations": db.investigation_stats(), "version": "1.0"}}

@router.put("/admin/settings")
def put_settings(body: SettingsIn):
    for k, v in body.model_dump(exclude_none=True).items():
        db.set_setting(k, str(v)); _audit(f"setting {k}={v}")
    runtime.reset(); return effective_settings()

@router.post("/admin/maintenance")
def run_maintenance():
    r = maintenance_once(); _audit(f"maintenance purged={r['purged']} trimmed={r['trimmed']}"); return r

@router.get("/admin/intel")
def threat_intel(): return intel.build(db.recent_events(5000))

@router.get("/admin/events")
def list_events(limit: int = 200): return db.recent_events(min(max(limit, 1), 1000))
@router.get("/admin/audit")
def audit(): return db.admin_log()
@router.get("/admin/geo")
def geo_summary(): return geo.summarize(db.recent_events(2000))

@router.get("/admin/report/{session}")
def report(session: str):
    rows = db.session_events(session)
    if not rows: return JSONResponse({"error": "unknown session"}, 404)
    labels = [r["label"] for r in rows]; stages = sorted(set(labels))
    risk = "high" if {"exploitation_attempt", "privilege_escalation_attempt"} & set(labels) else "medium" if "credential_probing" in labels else "low"
    return {"session": session, "events": len(rows), "ip": rows[0]["ip"], "stages_observed": stages, "risk": risk,
            "summary": f"{len(rows)} requests; observed attempts: {', '.join(stages)}. No successful compromise is claimed; decoy data only."}

@router.get("/admin/analyze/{session}")
def analyze_session(session: str):
    rows = db.session_events(session)
    if not rows: return JSONResponse({"error": "unknown session"}, 404)
    stored = db.get_investigation(session)  # written by the separate analyst service (which holds the LLM key)
    if stored and stored["n_events"] == len(rows): return json.loads(stored["payload"])
    return analyze(session, rows, None)

@router.get("/admin/replay/{session}")
def replay(session: str):
    rows = db.session_events(session)
    if not rows: return JSONResponse({"error": "unknown session"}, 404)
    t0 = rows[0]["ts"]
    return [{"t": round(r["ts"] - t0, 3), **{k: r[k] for k in ("method", "path", "label", "body")}} for r in rows]

@router.websocket("/ws")
async def ws(w: WebSocket):
    tok = os.environ.get("HIAB_ADMIN_TOKEN")
    if tok and w.query_params.get("token") != tok:
        await w.close(code=1008); return
    await w.accept(); clients.add(w)
    try:
        while True: await w.receive_text()
    except WebSocketDisconnect: clients.discard(w)

@router.get("/", response_class=HTMLResponse)
def dash(): return open(os.path.join(os.path.dirname(__file__), "dashboard.html")).read()

app = FastAPI(title="Honeypot-in-a-Box control plane", lifespan=lifespan)
@app.get("/healthz")
def healthz(): return {"ok": True}
app.include_router(router)
app.middleware("http")(admin_auth)
