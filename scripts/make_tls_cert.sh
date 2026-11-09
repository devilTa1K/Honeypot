#!/usr/bin/env bash
# Self-signed certificate for the admin listener (https://127.0.0.1:8443). Uses Docker, no local openssl needed.
set -euo pipefail; cd "$(dirname "$0")/.."
docker run --rm -v "$PWD/deploy/tls:/out" alpine/openssl req -x509 -newkey rsa:2048 -nodes -days 365 -subj "/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1" -keyout /out/server.key -out /out/server.crt
cp deploy/admin-tls.conf.template deploy/tls/admin-tls.conf
docker compose up -d proxy && docker compose exec -T proxy nginx -s reload
echo "Admin over TLS: https://127.0.0.1:8443 (self-signed: your browser will warn once). Use HIAB_API=https://127.0.0.1:8443 for the dashboard dev server."
