# One-command demo (Windows PowerShell). Needs Docker Desktop, Python with `pip install -r requirements.txt`.
$ErrorActionPreference = "Stop"; Set-Location (Split-Path $PSScriptRoot)
function Rand { -join ((48..57 + 65..90 + 97..122) | Get-Random -Count 24 | ForEach-Object { [char]$_ }) }
if (-not (Test-Path .env)) { "HIAB_ADMIN_TOKEN=$(Rand)`nHIAB_DB_PASSWORD=$(Rand)`nHIAB_REDIS_PASSWORD=$(Rand)`nHIAB_ANALYST_DB_PASSWORD=$(Rand)`nHIAB_INGEST_DB_PASSWORD=$(Rand)`nHIAB_CONTROL_DB_PASSWORD=$(Rand)" | Out-File -Encoding ascii .env; Write-Host "created .env with random secrets" }
$env:HIAB_ADMIN_TOKEN = ((Get-Content .env | Where-Object { $_ -like "HIAB_ADMIN_TOKEN=*" }) -split "=", 2)[1]
docker compose up --build -d --remove-orphans
if ($LASTEXITCODE -ne 0) { Write-Host "`nSTACK FAILED TO START. Status and recent logs:"; docker compose ps -a; docker compose logs --tail 25; Write-Host "`nIf db auth failed: an old volume has old passwords. Run: docker compose down -v --remove-orphans, then rerun."; exit 1 }
Write-Host "waiting for stack..."; for ($i = 0; $i -lt 60; $i++) { try { if ((curl.exe -s http://127.0.0.1:8088/healthz) -match "ok") { break } } catch {}; Start-Sleep 2 }
$env:HIAB_ADMIN_URL = "http://127.0.0.1:8090"
python scripts/attacker.py http://127.0.0.1:8088
python scripts/ssh_attacker.py
Write-Host "`nDashboard: cd frontend; npm install; `$env:HIAB_API='http://127.0.0.1:8090'; npm run dev  -> http://localhost:5173 (token: $env:HIAB_ADMIN_TOKEN)"
