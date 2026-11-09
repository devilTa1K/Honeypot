# Automated release checks for the running Docker stack (Windows PowerShell). Run after scripts\demo.ps1.
Set-Location (Split-Path $PSScriptRoot)
$token = ((Get-Content .env | Where-Object { $_ -like "HIAB_ADMIN_TOKEN=*" }) -split "=", 2)[1]
$script:bad = 0
function Check($name, $ok) { if ($ok) { Write-Host "PASS  $name" -ForegroundColor Green } else { Write-Host "FAIL  $name" -ForegroundColor Red; $script:bad++ } }
function Dx($svc, [string[]]$cmd) { $o = & docker compose exec -T $svc @cmd 2>&1 | Out-String; return @{ code = $LASTEXITCODE; out = $o } }
$ins = "import time; from app import db; db.insert_event(dict(ts=time.time(),session='verifyverify',ip='0.0.0.0',method='VERIFY',path='/verify',ua='',body='',label='reconnaissance'))"

Check "admin API without token is rejected (401)" ((curl.exe -s -o NUL -w "%{http_code}" http://127.0.0.1:8090/admin/events) -eq "401")
Check "public decoy listener has no route to the admin API (404)" ((curl.exe -s -o NUL -w "%{http_code}" http://127.0.0.1:8088/admin/events) -eq "404")
Check "public decoy listener serves the fake portal, not the SOC dashboard" ((curl.exe -s http://127.0.0.1:8088/) -match "employee portal")
Check "decoy runs as uid 10001" ((Dx decoy @("id", "-u")).out.Trim() -eq "10001")
Check "decoy root filesystem is read-only" ((Dx decoy @("sh", "-c", "touch /srv/x")).code -ne 0)
Check "decoy has no internet" ((Dx decoy @("python", "-c", "import urllib.request;urllib.request.urlopen('http://1.1.1.1',timeout=3)")).code -ne 0)
Check "decoy cannot reach the control plane" ((Dx decoy @("python", "-c", "import urllib.request;urllib.request.urlopen('http://control:8001/healthz',timeout=3)")).code -ne 0)
Check "decoy has no admin token or LLM key" ((Dx decoy @("env")).out -notmatch "HIAB_ADMIN_TOKEN|ANTHROPIC_API_KEY")
$r = Dx decoy @("python", "-c", "from app import db; db.recent_events()")
Check "decoy DB role cannot read events" (($r.code -ne 0) -and ($r.out -match "permission denied"))
Check "decoy DB role can insert events" ((Dx decoy @("python", "-c", $ins)).code -eq 0)
$r = Dx control @("python", "-c", $ins)
Check "control DB role cannot insert events" (($r.code -ne 0) -and ($r.out -match "permission denied"))
Check "control DB role can read events" ((Dx control @("python", "-c", "from app import db; db.recent_events(1)")).code -eq 0)
Check "redis CONFIG command is disabled" ((Dx redis @("redis-cli", "config", "get", "dir")).out -match "unknown command")
Check "migrate job exited 0" ((docker inspect -f '{{.State.ExitCode}}' (docker compose ps -a -q migrate)) -eq "0")
Check "analyst service is running" ((docker compose ps analyst --format "{{.State}}") -match "running")

Check "environments API lists the active company" ((curl.exe -s -H "x-admin-token: $token" http://127.0.0.1:8090/admin/environments) -match "acme-pay")
Check "threat-intel and settings endpoints answer (200)" (((curl.exe -s -o NUL -w "%{http_code}" -H "x-admin-token: $token" http://127.0.0.1:8090/admin/intel) -eq "200") -and ((curl.exe -s -o NUL -w "%{http_code}" -H "x-admin-token: $token" http://127.0.0.1:8090/admin/settings) -eq "200"))
Check "decoy serves fake repos and has no admin settings route" (((curl.exe -s http://127.0.0.1:8088/repos) -match "acme-pay-api") -and ((curl.exe -s -o NUL -w "%{http_code}" http://127.0.0.1:8088/admin/settings) -eq "404"))
if (Test-Path deploy/tls/server.crt) { Check "admin TLS listener answers" ((curl.exe -sk https://127.0.0.1:8443/healthz) -match "ok") }

curl.exe -s -o NUL -X POST -H "x-admin-token: $token" "http://127.0.0.1:8090/admin/kill"; Start-Sleep 3
Check "kill switch: decoy returns 503" ((curl.exe -s -o NUL -w "%{http_code}" http://127.0.0.1:8088/wiki) -eq "503")
curl.exe -s -o NUL -X POST -H "x-admin-token: $token" "http://127.0.0.1:8090/admin/company?name=Acme%20Pay"; Start-Sleep 3
Check "decoy recovers after redeploy (200)" ((curl.exe -s -o NUL -w "%{http_code}" http://127.0.0.1:8088/wiki) -eq "200")

if ($script:bad -eq 0) { Write-Host "`nALL CHECKS PASSED" -ForegroundColor Green } else { Write-Host "`n$($script:bad) CHECK(S) FAILED: send me this output plus: docker compose logs --tail 30" -ForegroundColor Red }
