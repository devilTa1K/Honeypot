"""Separate analyst service. Holds the LLM key and has egress, but has no inbound port and read-only access to events (least-privilege DB role).
The decoy app never calls it or sees the key: it only reads the stored investigations."""
import json, os, time
os.environ.setdefault("HIAB_SKIP_MIGRATE", "1")
from . import db
from .analyst import analyze, get_provider

def run_once(provider, idle_secs: float = 30) -> int:
    n = 0
    for sid, _ in db.sessions_needing_analysis(idle_secs):
        rows = db.session_events(sid)
        inv = analyze(sid, rows, provider)
        db.save_investigation(sid, len(rows), inv.source, inv.model_dump_json()); n += 1
    return n

def main() -> None:
    provider = get_provider()
    print("analyst worker:", "LLM enabled" if provider else "no ANTHROPIC_API_KEY, idling", flush=True)
    while True:
        try:
            if provider: print("analysed", run_once(provider), "sessions", flush=True)
        except Exception as e:
            print("worker error:", type(e).__name__, flush=True)
        time.sleep(15)

if __name__ == "__main__":
    main()
