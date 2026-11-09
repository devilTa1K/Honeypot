"""Structured JSON logging to stdout. Never log request bodies or captured passwords."""
import json, logging, os, sys, time

class JsonFormatter(logging.Formatter):
    def format(self, r: logging.LogRecord) -> str:
        d = {"ts": round(time.time(), 3), "level": r.levelname, "logger": r.name, "msg": r.getMessage(), **getattr(r, "fields", {})}
        if r.exc_info: d["exc"] = self.formatException(r.exc_info)
        return json.dumps(d, default=str)

def get(name: str) -> logging.Logger:
    root = logging.getLogger("hiab")
    if not root.handlers:
        h = logging.StreamHandler(sys.stdout); h.setFormatter(JsonFormatter()); root.addHandler(h)
        root.setLevel(os.environ.get("HIAB_LOG_LEVEL", "INFO")); root.propagate = False
    return logging.getLogger("hiab." + name)
