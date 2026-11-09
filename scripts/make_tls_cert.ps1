# Self-signed certificate for the admin listener (https://127.0.0.1:8443). Uses Docker, no local openssl needed.
Set-Location (Split-Path $PSScriptRoot)
docker run --rm -v "${PWD}/deploy/tls:/out" alpine/openssl req -x509 -newkey rsa:2048 -nodes -days 365 -subj "/CN=localhost" -addext "subjectAltName=DNS:localhost,IP:127.0.0.1" -keyout /out/server.key -out /out/server.crt
if ($LASTEXITCODE -ne 0) { Write-Host "certificate generation failed"; exit 1 }
Copy-Item deploy/admin-tls.conf.template deploy/tls/admin-tls.conf -Force
docker compose up -d proxy; docker compose exec -T proxy nginx -s reload
Write-Host "Admin over TLS: https://127.0.0.1:8443 (self-signed: browser warns once). Dashboard dev server: `$env:HIAB_API='https://127.0.0.1:8443'"
