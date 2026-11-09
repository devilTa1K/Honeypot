# Honeypot-in-a-Box
AI-assisted cyber deception platform: generates a fictional company, serves decoy HTTP and SSH services, captures and classifies every interaction (attempts only, never successes), and shows it in a live SOC dashboard with replay and investigation summaries.

## Quick start
```
pip install -r requirements.txt
python -m pytest -q                       # SQLite; Postgres/Redis tests run when TEST_DATABASE_URL / REDIS_URL_TEST are set
scripts/demo.ps1                          # or scripts/demo.sh: full Docker stack + both test attackers
scripts/verify_stack.ps1                  # automated isolation / role / kill-switch checks
cd frontend && npm install && npm run dev # SOC dashboard (set HIAB_API=http://127.0.0.1:8090 for the Docker stack)
```
Ports: **8088** public decoy (HTTP), **2222** SSH decoy, **8090** admin/SOC (loopback only; never expose).
```
```
Lightweight dev server without Docker: `python -m uvicorn app.main:app --port 8000` (SQLite, in-process fan-out, no SSH unless `HIAB_SSH_PORT` is set).

## Docs
`docs/ARCHITECTURE.md` · `docs/THREAT_MODEL.md` · `docs/API.md` · `docs/SCHEMA.md` · `docs/DEMO.md` · `docs/RELEASE_CHECKLIST.md`

## Verification status (be skeptical, re-run the checklist)
| Area | Status |
|---|---|
| Tests (38, incl. real SSH client, PROXY protocol, Postgres role separation, hardened Redis, environments, intel, settings, decoys) | all pass with real Postgres+Redis in my sandbox; the rest pass and 3 skip without them |
| Split architecture end to end (real nginx -> decoy + control processes, Postgres roles, Redis relay, SSH via PROXY protocol, kill switch) | verified in my sandbox; real client IPs preserved for HTTP and SSH |
| Alembic migrations, hostile-input handling, analyst DB role | verified on SQLite and PostgreSQL 16 |
| Redis pub/sub -> WebSocket relay, rate limit | verified with a real Redis |
| nginx admin allowlist and stream/PROXY config | verified with a real nginx (syntax and live request test) |
| First two Docker milestones (isolation, uid, read-only FS, no egress) | verified on the author's Docker Desktop |
| 7-service compose stack on Docker Desktop (Windows) | **ran on the author's machine**: all services healthy, HTTP and SSH attackers captured through the proxy, 15/15 automated isolation, role-separation and kill-switch checks passed (`scripts/verify_stack.ps1`, now 17 checks incl. the listener split) |
| LLM calls, GeoIP database, UI visuals | **not exercised** (no key, no database, no browser in my sandbox) |

## Known limitations
See the end of `docs/THREAT_MODEL.md`. Biggest: no TLS; a decoy compromise can poison the live feed; Docker Desktop NAT hides real client IPs locally.

## 3D globe (Overview page)
Interactive Three.js globe (satellite imagery, city lights, atmosphere, country borders, animated attack arcs ending at the honeypot). Markers appear only for **public IPs that a GeoIP database can locate** (`HIAB_GEOIP_DB`); a checkbox shows clearly labelled **simulated** sample attacks for demos and screenshots. Set `VITE_HONEYPOT_LAT` / `VITE_HONEYPOT_LON` before `npm run dev` to place the honeypot. A 2D map is the automatic fallback if WebGL is unavailable.
Imagery credit: NASA Visible Earth (Blue Marble / Black Marble), as distributed in the `three-globe` example images (MIT); resized copies live in `frontend/src/assets/`.

## Features
Decoys: HTTP (fake portal, wiki, directory, `.env`, source repos, git metadata, admin/WordPress/phpMyAdmin/cloud-console logins, fake AWS API) and SSH (simulated shell). SOC dashboard: Overview (counters, timeline, 3D globe), Live Monitor, Session Replay with analyst report, Event Explorer, Threat Intel, Environments, Generator, Settings. Per-company dedicated containers via `scripts/provision.py`. Optional admin TLS via `scripts/make_tls_cert.*`.

## Not built / not possible here
- **Screenshots**: `scripts/screenshots.mjs` exists but has not been run (no browser in the build sandbox); `docs/screenshots/` is empty until you run it.
- **Event signing**: deliberately omitted (a compromised decoy would hold the key); see the threat model.
- **Untested on Docker by the author**: `scripts/provision.py` and the TLS script (their output files and nginx syntax are tested).
- **Never rendered in a browser by the author**: the Environments, Threat Intel and Settings pages and the 3D globe (they typecheck and build).
- Quota is by event count, not bytes; the LLM analyst and GeoIP lookups need your own key/database.
