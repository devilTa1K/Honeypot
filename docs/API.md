# HTTP API
In Docker the **decoy** (`app.decoy`, 8000) and **control plane** (`app.control`, 8001) are separate processes behind nginx: decoy on 8088 (public), admin on 8090 (loopback) and 8443 (optional TLS). `app.main` combines both for dev/tests. Admin calls need header `x-admin-token`; `/ws?token=...` streams live events. The decoy exposes no docs and no admin routes.

| Method | Path | Served by |
|---|---|---|
| GET | `/` | both / health |
| GET | `/.env` | decoy (public, logged and classified) |
| GET | `/.git/HEAD` | decoy (public, logged and classified) |
| GET | `/.git/config` | decoy (public, logged and classified) |
| GET | `/admin-panel` | control plane (token; loopback/TLS listener) |
| GET | `/admin-panel/` | control plane (token; loopback/TLS listener) |
| POST | `/admin-panel/login` | control plane (token; loopback/TLS listener) |
| GET | `/admin/analyze/{session}` | control plane (token; loopback/TLS listener) |
| GET | `/admin/audit` | control plane (token; loopback/TLS listener) |
| POST | `/admin/company` | control plane (token; loopback/TLS listener) |
| GET | `/admin/environments` | control plane (token; loopback/TLS listener) |
| POST | `/admin/environments` | control plane (token; loopback/TLS listener) |
| DELETE | `/admin/environments/{slug}` | control plane (token; loopback/TLS listener) |
| POST | `/admin/environments/{slug}/activate` | control plane (token; loopback/TLS listener) |
| POST | `/admin/environments/{slug}/port` | control plane (token; loopback/TLS listener) |
| POST | `/admin/environments/{slug}/status` | control plane (token; loopback/TLS listener) |
| GET | `/admin/events` | control plane (token; loopback/TLS listener) |
| GET | `/admin/geo` | control plane (token; loopback/TLS listener) |
| GET | `/admin/intel` | control plane (token; loopback/TLS listener) |
| POST | `/admin/kill` | control plane (token; loopback/TLS listener) |
| POST | `/admin/maintenance` | control plane (token; loopback/TLS listener) |
| GET | `/admin/replay/{session}` | control plane (token; loopback/TLS listener) |
| GET | `/admin/report/{session}` | control plane (token; loopback/TLS listener) |
| GET | `/admin/settings` | control plane (token; loopback/TLS listener) |
| PUT | `/admin/settings` | control plane (token; loopback/TLS listener) |
| GET | `/api/aws/instances` | decoy (public, logged and classified) |
| GET | `/api/customers` | decoy (public, logged and classified) |
| GET | `/api/users` | decoy (public, logged and classified) |
| GET | `/backup/` | decoy (public, logged and classified) |
| GET | `/console` | decoy (public, logged and classified) |
| GET | `/directory` | decoy (public, logged and classified) |
| GET | `/healthz` | both / health |
| POST | `/login` | decoy (public, logged and classified) |
| GET | `/phpmyadmin/` | decoy (public, logged and classified) |
| GET | `/repos` | decoy (public, logged and classified) |
| GET | `/repos/{name}` | decoy (public, logged and classified) |
| GET | `/repos/{name}/blob/{path}` | decoy (public, logged and classified) |
| GET | `/robots.txt` | decoy (public, logged and classified) |
| GET | `/wiki` | decoy (public, logged and classified) |
| GET | `/wp-login.php` | decoy (public, logged and classified) |

Notable admin endpoints: `/admin/environments*` (create, activate, start/stop, port, delete), `/admin/intel` (aggregated threat intelligence), `/admin/settings` (rate limit, retention, event quota), `/admin/maintenance`, `/admin/analyze/{session}`, `/admin/replay/{session}`, `/admin/geo`.
Event labels: `reconnaissance`, `enumeration`, `credential_probing`, `data_discovery_attempt`, `exploitation_attempt`, `privilege_escalation_attempt` (attempts only). SSH events: `method` `SSH-AUTH` or `SSH`.
