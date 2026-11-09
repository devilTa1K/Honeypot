"""Provision a per-company decoy container on the HOST (the control plane never gets Docker access).
  python scripts/provision.py up <slug> [--dry-run]    render files, start decoy-<slug>, add its proxy listener, mark it running
  python scripts/provision.py down <slug> [--dry-run]  stop it, remove its files, reload the proxy, mark it stopped
Create the environment first in the dashboard (Generator or Environment Manager). Needs HIAB_ADMIN_TOKEN (env or .env)."""
import glob, os, subprocess, sys
from pathlib import Path
import httpx
ROOT = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(ROOT))
from app.provision import PORT_RANGE, render_compose, render_nginx, service_name

def token() -> str:
    if os.environ.get("HIAB_ADMIN_TOKEN"): return os.environ["HIAB_ADMIN_TOKEN"]
    for line in (ROOT / ".env").read_text().splitlines():
        if line.startswith("HIAB_ADMIN_TOKEN="): return line.split("=", 1)[1].strip()
    sys.exit("HIAB_ADMIN_TOKEN not found")

def main() -> None:
    if len(sys.argv) < 3 or sys.argv[1] not in ("up", "down"): sys.exit(__doc__)
    action, slug, dry = sys.argv[1], sys.argv[2], "--dry-run" in sys.argv
    admin, h = os.environ.get("HIAB_ADMIN_URL", "http://127.0.0.1:8090"), {"x-admin-token": token()}
    envs = httpx.get(f"{admin}/admin/environments", headers=h).json()
    env = next((e for e in envs if e["id"] == slug), None)
    if env is None: sys.exit(f"unknown environment '{slug}'. Create it in the dashboard first.")
    envdir = ROOT / "deploy" / "envs"; yml, conf = envdir / f"{slug}.yml", envdir / f"{slug}.nginx.conf"
    def compose(*args: str) -> list[str]:
        files = [f for p in sorted(glob.glob(str(envdir / "*.yml"))) for f in ("-f", p)]
        return ["docker", "compose", "-f", "docker-compose.yml", *files, *args]
    def run(cmd: list[str]) -> None:
        print("$", " ".join(cmd)); 
        if not dry: subprocess.run(cmd, cwd=ROOT, check=True)
    if action == "up":
        used = {e["port"] for e in envs if e["port"] and e["id"] != slug}
        port = env["port"] or next((p for p in PORT_RANGE if p not in used), None)
        if port is None: sys.exit("no free port in %d-%d" % (PORT_RANGE.start, PORT_RANGE.stop - 1))
        print(f"writing {yml.name} and {conf.name} (port {port})")
        if not dry: yml.write_text(render_compose(slug)); conf.write_text(render_nginx(slug, port))
        if not dry: httpx.post(f"{admin}/admin/environments/{slug}/port", params={"value": port}, headers=h).raise_for_status()
        run(compose("up", "-d", "--build", service_name(slug))); run(["docker", "compose", "exec", "-T", "proxy", "nginx", "-s", "reload"])
        if not dry: httpx.post(f"{admin}/admin/environments/{slug}/status", params={"value": "running"}, headers=h).raise_for_status()
        print(f"decoy for '{slug}' on http://127.0.0.1:{port}")
    else:
        run(compose("stop", service_name(slug))); run(compose("rm", "-f", service_name(slug)))
        if not dry:
            yml.unlink(missing_ok=True); conf.unlink(missing_ok=True)
            httpx.post(f"{admin}/admin/environments/{slug}/status", params={"value": "stopped"}, headers=h).raise_for_status()
        run(["docker", "compose", "exec", "-T", "proxy", "nginx", "-s", "reload"])

if __name__ == "__main__": main()
