"""Controlled test attacker. Only targets the URL you pass; refuses non-local hosts unless --allow-remote."""
import os, sys, time, httpx
from urllib.parse import urlparse
base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
host = urlparse(base).hostname
if host not in ("127.0.0.1", "localhost", "proxy", "app") and "--allow-remote" not in sys.argv:
    sys.exit("refusing non-local target")
admin = os.environ.get("HIAB_ADMIN_URL", base)   # Docker stack: http://127.0.0.1:8090
tok = {"x-admin-token": __import__("os").environ.get("HIAB_ADMIN_TOKEN", "")}
httpx.post(f"{admin}/admin/company", params={"name": "Acme Pay", "industry": "Fintech", "size": 40}, headers=tok)
c = httpx.Client(base_url=base)
steps = [("GET", "/robots.txt", None), ("GET", "/wiki", None), ("GET", "/directory", None),
         ("POST", "/login", {"user": "admin", "password": "admin"}), ("POST", "/login", {"user": "admin", "password": "Winter2026!"}),
         ("GET", "/.env", None), ("GET", "/api/customers", None), ("GET", "/files?name=../../etc/passwd", None)]
for m, path, body in steps:
    r = c.request(m, path, json=body); print(m, path, r.status_code); time.sleep(0.2)
sid = c.cookies.get("sid")
print(httpx.get(f"{admin}/admin/report/{sid}", headers=tok).json())
print(httpx.get(f"{admin}/admin/replay/{sid}", headers=tok).json()[:3], "...")
