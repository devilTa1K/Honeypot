# Release checklist
**Fast path:** after `scripts\demo.ps1`, run `scripts\verify_stack.ps1` (17 automated checks: isolation, uid, read-only FS, DB role separation, Redis hardening, kill switch). It adds one harmless `VERIFY` event. The manual list below is the full set.

- [ ] `python -m pytest -q` passes; with `TEST_DATABASE_URL` and `REDIS_URL_TEST` set, no tests are skipped
- [ ] `cd frontend && npm ci && npm run build` succeeds
- [ ] `docker compose config -q` is clean; `docker compose up --build -d` ends with db, redis, decoy (healthy), control (healthy), analyst, proxy running; `migrate` exited 0 (`docker compose ps -a`)
- [ ] `curl.exe http://127.0.0.1:8088/` shows the fake portal; `http://127.0.0.1:8088/admin/events` -> 404; `http://127.0.0.1:8090/admin/events` without token -> 401; keep 8090 on loopback
- [ ] Decoy has no internet: `docker compose exec decoy python -c "import urllib.request;urllib.request.urlopen('http://1.1.1.1',timeout=3)"` fails
- [ ] App runs as uid 10001 with a read-only FS (`docker compose exec decoy id`; `touch /srv/x` fails)
- [ ] Least privilege: `docker compose exec db psql -U hiab_ingest -d hiab -c "select count(*) from events"` is denied (use the ingest password); decoy env has no `HIAB_ADMIN_TOKEN` or `ANTHROPIC_API_KEY` (`docker compose exec decoy env`)
- [ ] Analyst can reach the internet only when a key is set; `docker compose logs analyst` shows no errors
- [ ] `python scripts/ssh_attacker.py` works through the proxy; the stored `ip` is the client address, not the proxy's (on Docker Desktop it may be the NAT gateway; on Linux it should be the real client)
- [ ] Dashboard: all five pages load; kill switch returns 503 on decoys
- [ ] Rotate every secret in `.env`; never commit `.env`; add TLS before any non-local exposure
- [ ] Screenshots regenerated; known limitations in `docs/THREAT_MODEL.md` still accurate
- [ ] `python scripts/provision.py up acme-pay` starts `decoy-acme-pay` (check `docker compose ps`) and `http://127.0.0.1:8101/` answers; `down` removes it. (Not run on Docker by the author.)
- [ ] `scripts\make_tls_cert.ps1` then `curl.exe -k https://127.0.0.1:8443/healthz` -> `{"ok":true}`
- [ ] Settings page: change the rate limit, save, confirm the decoy honours it; Environments page: activate/stop/delete work
