#!/usr/bin/env bash
# One-command demo (Linux/macOS). Needs Docker and `pip install -r requirements.txt`.
set -euo pipefail; cd "$(dirname "$0")/.."
rnd() { LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 24; }
[ -f .env ] || { printf 'HIAB_ADMIN_TOKEN=%s\nHIAB_DB_PASSWORD=%s\nHIAB_REDIS_PASSWORD=%s\nHIAB_ANALYST_DB_PASSWORD=%s\nHIAB_INGEST_DB_PASSWORD=%s\nHIAB_CONTROL_DB_PASSWORD=%s\n' "$(rnd)" "$(rnd)" "$(rnd)" "$(rnd)" "$(rnd)" "$(rnd)" > .env; echo "created .env"; }
export HIAB_ADMIN_TOKEN="$(grep '^HIAB_ADMIN_TOKEN=' .env | cut -d= -f2)"
docker compose up --build -d --remove-orphans || { docker compose ps -a; docker compose logs --tail 25; echo "If db auth failed: docker compose down -v --remove-orphans, then rerun."; exit 1; }
for i in $(seq 60); do curl -s http://127.0.0.1:8088/healthz | grep -q ok && break; sleep 2; done
HIAB_ADMIN_URL=http://127.0.0.1:8090 python scripts/attacker.py http://127.0.0.1:8088
python scripts/ssh_attacker.py
echo "Dashboard: cd frontend && npm install && HIAB_API=http://127.0.0.1:8090 npm run dev  (token: $HIAB_ADMIN_TOKEN)"
