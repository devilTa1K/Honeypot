# Demonstration script (about 5 minutes)
1. `scripts/demo.ps1` (Windows) or `scripts/demo.sh`: creates `.env` with random secrets, builds and starts db, redis, migrate, decoy, control, analyst, proxy, then runs both test attackers.
2. Start the UI: `cd frontend && npm install && $env:HIAB_API="http://127.0.0.1:8090"; npm run dev`, open http://localhost:5173, paste the admin token from `.env`.
3. **Generator**: create a company (e.g. "Acme Pay"); the decoy environment is live.
4. Re-run ``$env:HIAB_ADMIN_URL="http://127.0.0.1:8090"; python scripts/attacker.py http://127.0.0.1:8088` and `python scripts/ssh_attacker.py` while watching **Live Monitor** (events arrive over WebSocket via Redis).
5. **Overview**: counters, classification bars, timeline. The map stays empty locally (private IPs); with a GeoIP database and public traffic, points appear.
6. **Session Replay**: pick the SSH session, press Play, then read the investigation (risk, ATT&CK tactics, recommendations, `deterministic` or `llm` badge).
7. Set `ANTHROPIC_API_KEY` in `.env`, `docker compose up -d`; after a session goes idle for 30 s the analyst service stores an `llm` investigation.
8. Press **EMERGENCY SHUTDOWN**: decoys return 503 and SSH logins are refused.
9. Optional: `node scripts/screenshots.mjs` (see the file header) to regenerate `docs/screenshots/`.

## Extra steps for the newer pages
10. **Environments**: create a second company, Activate it, and watch the decoy portal change (`http://127.0.0.1:8088/`). Stop it and the decoy returns 503.
11. **Threat Intel**: after both attackers ran, see top sources, the credentials tried, the `wget` URL as an IOC, and ATT&CK tactics.
12. **Settings**: lower the rate limit to 5, repeat the attacker, and see fewer stored events. Press *Run cleanup now*.
13. Richer decoys: `curl.exe http://127.0.0.1:8088/robots.txt`, then `/repos`, `/repos/acme-pay-api/blob/config.py`, `/.git/config`, `/admin-panel`. All are logged and classified.
14. Dedicated container: `python scripts/provision.py up acme-pay`, then open the printed port.
15. TLS: `scripts\make_tls_cert.ps1`, then `https://127.0.0.1:8443`.
