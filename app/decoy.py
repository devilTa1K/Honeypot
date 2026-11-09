"""Public-facing decoy process: fake company services + fake SSH. It has no admin routes, no admin token, no LLM key, and an insert-only DB role."""
import os, re, time, uuid
from contextlib import asynccontextmanager
from fastapi import APIRouter, FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from . import bus, runtime
from .classifier import classify
from .generator import repo_files
from .events import client_ip, emit

router = APIRouter()
def co(): return runtime.company()

@router.get("/directory")
def directory(): return [e.model_dump() for e in co().employees]
@router.get("/wiki")
def wiki(): return {"title": f"{co().name} Internal Wiki", "pages": ["Onboarding", "VPN setup", "Deploy runbook"]}
@router.get("/.env")
def env(): return Response(f"AWS_ACCESS_KEY_ID={co().aws_key_id}\nAWS_SECRET_ACCESS_KEY={co().aws_secret}\n", media_type="text/plain")
@router.get("/api/customers")
def customers(): return [{"id": i, "name": f"Customer {i}", "balance": 1000 + i * 37} for i in range(1, 6)]
@router.post("/login")
async def login(request: Request): return JSONResponse({"error": "invalid credentials"}, 401)

def _login(title: str, action: str) -> str:
    return (f"<html><head><title>{title}</title></head><body><h2>{title}</h2><form method='post' action='{action}'>"
            "<input name='username' placeholder='username'><input name='password' type='password' placeholder='password'><button>Sign in</button></form></body></html>")

@router.get("/robots.txt")
def robots(): return PlainTextResponse("User-agent: *\nDisallow: /admin-panel/\nDisallow: /repos/\nDisallow: /backup/\n")
@router.get("/admin-panel", response_class=HTMLResponse)
@router.get("/admin-panel/", response_class=HTMLResponse)
def admin_panel(): return _login(f"{co().name} Admin", "/admin-panel/login")
@router.post("/admin-panel/login")
async def admin_panel_login(): return JSONResponse({"error": "invalid credentials"}, 401)
@router.get("/wp-login.php", response_class=HTMLResponse)
def wp_login(): return _login("WordPress", "/wp-login.php")
@router.get("/phpmyadmin/", response_class=HTMLResponse)
def phpmyadmin(): return _login("phpMyAdmin", "/phpmyadmin/index.php")
@router.get("/console", response_class=HTMLResponse)
def console(): return _login(f"{co().name} Cloud Console", "/console/signin")
@router.get("/api/aws/instances")
def instances(): return {"Reservations": [{"Instances": [{"InstanceId": f"i-0{n}a1b2c3d4e5f6", "PrivateIpAddress": f"10.0.1.{10 + n}",
    "Tags": [{"Key": "Name", "Value": f"prod-{role}"}]} for n, role in enumerate(("api-01", "db-01", "bastion"))]}]}
@router.get("/api/users")
def users(): return [{"name": e.name, "email": e.email, "dept": e.dept} for e in co().employees[:20]]
@router.get("/backup/", response_class=HTMLResponse)
def backups(): return "<h1>Index of /backup</h1><a href='db-2026-10-01.sql.gz'>db-2026-10-01.sql.gz</a><br><a href='site.bak'>site.bak</a>"
@router.get("/.git/HEAD")
def git_head(): return PlainTextResponse("ref: refs/heads/main\n")
@router.get("/.git/config")
def git_config(): return PlainTextResponse(f"[core]\n\trepositoryformatversion = 0\n[remote \"origin\"]\n\turl = git@git.{co().domain}:{co().repos[0]}.git\n")
@router.get("/repos")
def repos(): return [{"name": r, "url": f"/repos/{r}"} for r in co().repos]
@router.get("/repos/{name}")
def repo(name: str):
    files = repo_files(co()).get(name)
    if files is None: raise HTTPException(404)
    return {"name": name, "files": sorted(files)}
@router.get("/repos/{name}/blob/{path:path}")
def blob(name: str, path: str):
    text = repo_files(co()).get(name, {}).get(path)   # dictionary lookup only: no filesystem access
    if text is None: raise HTTPException(404)
    return PlainTextResponse(text)

def make_capture(skip: tuple[str, ...]):
    async def capture(request: Request, call_next):
        p = request.url.path
        if p in skip or any(len(s) > 1 and s.endswith("/") and p.startswith(s) for s in skip):
            return await call_next(request)
        if runtime.is_killed() or runtime.company() is None:
            return Response("Service unavailable", 503)
        body = (await request.body()).decode(errors="replace")[:2000]
        cookie = request.cookies.get("sid", "")
        sid = cookie if re.fullmatch(r"[0-9a-f]{12}", cookie) else uuid.uuid4().hex[:12]  # never trust attacker-supplied ids
        ev = dict(ts=time.time(), session=sid, ip=client_ip(request), method=request.method[:16], path=p, ua=request.headers.get("user-agent", ""),
                  body=body, label=classify(p + ("?" + request.url.query if request.url.query else ""), body))
        if await bus.allow(ev["ip"], runtime.setting_int("rate_per_min", int(os.environ.get("HIAB_RATE_PER_MIN", "300")))): await emit(ev)
        resp = await call_next(request); resp.set_cookie("sid", sid, httponly=True); return resp
    return capture

@asynccontextmanager
async def lifespan(_app):
    srv = None
    if os.environ.get("HIAB_SSH_PORT"):
        from .sshpot import start_ssh
        srv = await start_ssh(emit, lambda: not runtime.is_killed(), port=int(os.environ["HIAB_SSH_PORT"]),
                              proxy_protocol=os.environ.get("HIAB_SSH_PROXY_PROTOCOL") == "1")
    yield
    if srv: srv.close()

app = FastAPI(title="decoy", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
@app.get("/healthz")
def healthz(): return {"ok": True}
@app.get("/", response_class=HTMLResponse)
def home(): return f"<h1>{co().name}</h1><p>Internal employee portal. <a href='/login'>Sign in</a></p>"
app.include_router(router)
app.middleware("http")(make_capture(("/healthz",)))
