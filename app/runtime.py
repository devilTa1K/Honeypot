"""Shared state lives in the database so decoy and control processes stay in sync (cached HIAB_STATE_TTL seconds).
A decoy serves HIAB_ENV_ID if set (per-environment container), otherwise the globally active environment."""
import os, time
from . import db
from .generator import Company, generate_company
_c: dict = {"t": -1e9, "company": None, "killed": False, "env": "", "settings": {}}

def _refresh() -> None:
    if time.time() - _c["t"] < float(os.environ.get("HIAB_STATE_TTL", "2")): return
    s = db.all_settings(); slug = os.environ.get("HIAB_ENV_ID") or s.get("active_env") or ""
    row = db.get_environment(slug) if slug else None
    _c.update(t=time.time(), settings=s, env=slug if row else "", killed=s.get("killed") == "1" or bool(row and row["status"] == "stopped"),
              company=generate_company(row["name"], row["industry"], row["size"]) if row else None)

def company() -> Company | None: _refresh(); return _c["company"]
def is_killed() -> bool: _refresh(); return _c["killed"]
def env_name() -> str: _refresh(); return _c["env"]
def setting_int(key: str, default: int) -> int:
    _refresh()
    try: return int(_c["settings"][key])
    except (KeyError, ValueError): return default
def reset() -> None: _c.update(t=-1e9, company=None, killed=False, env="", settings={})
