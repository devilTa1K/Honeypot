"""Combined dev/test app (decoy + control in one process, SQLite). The Docker stack runs app.decoy and app.control as separate services."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from . import control, decoy

@asynccontextmanager
async def lifespan(app):
    async with control.lifespan(app), decoy.lifespan(app):
        yield

app = FastAPI(title="Honeypot-in-a-Box (combined)", lifespan=lifespan)
@app.get("/healthz")
def healthz(): return {"ok": True}
app.include_router(control.router)   # control first: "/" is the dashboard here
app.include_router(decoy.router)
app.middleware("http")(control.admin_auth)
app.middleware("http")(decoy.make_capture(("/admin/", "/ws", "/docs", "/openapi.json", "/", "/healthz")))
