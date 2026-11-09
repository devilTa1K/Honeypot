# Threat model
**Assets:** host and LAN, admin token, LLM API key, database, trust in captured data.  **Boundaries:** internet -> proxy -> decoy app (internal net) -> data net; analyst on a separate egress net.
Status key: **verified** = ran against real components in my sandbox; **tested** = automated test; **config** = configuration written and syntax-checked, not run end-to-end; **open** = not mitigated.

| Threat | Mitigation | Status |
|---|---|---|
| Container escape / host access | non-root, read-only rootfs, caps dropped, no-new-privileges, mem/cpu/pid limits, no Docker socket/host mounts | verified on the author's Docker stack (`verify_stack.ps1`): uid 10001, read-only FS; db/redis/analyst hardening runs but is not individually probed |
| Pivot/outbound abuse from decoy | decoy and data networks `internal: true` | verified on the author's Docker stack (`verify_stack.ps1`): decoy has no internet |
| LLM key theft via decoy compromise | key lives only in the analyst service; app never calls the LLM and has no inbound path from it | **tested** (worker stores LLM result, app never calls it); verified on the author's Docker stack (`verify_stack.ps1`): decoy has no key or admin token in its environment |
| Attacker reaches admin API/docs | decoy process has no admin routes or docs; control plane needs a token; the public nginx listener has no route to the control plane at all; the admin listener (8090) is loopback-published and keeps a private-source allowlist | **tested** (separate apps); verified on the author's Docker stack (`verify_stack.ps1`): the public listener (8088) returns 404 for `/admin/events` and serves the fake portal, admin API needs a token on loopback-only port 8090 |
| Decoy pivots to control/analyst | decoy shares no network with control or analyst (separate `db_ingest` / `db_ctl` networks); control and decoy only meet at Postgres/Redis | verified on the author's Docker stack (`verify_stack.ps1`) |
| Decoy compromise reaches data | decoy DB role is INSERT-only on events (cannot read events, change settings or audit); owner credentials exist only in the short-lived migrate job | **verified** on PostgreSQL 16 (role test) and verified on the author's Docker stack (`verify_stack.ps1`) |
| Control/analyst abuse | `hiab_control` cannot insert events; `hiab_analyst` cannot insert/delete/drop events | **verified** on PostgreSQL 16 |
| Redis abuse from decoy | password, CONFIG/DEBUG/FLUSH*/REPLICAOF/MODULE disabled, internal network | verified on the author's Docker stack (`verify_stack.ps1`): CONFIG disabled |
| Kill switch not reaching decoy | state in DB, decoy refreshes every 2 s, SSH logins refused | verified on the author's Docker stack (`verify_stack.ps1`): 503 within 3 s, recovers after redeploy |
| Hostile input: NUL bytes, oversize fields, forged session ids, huge method names | cleaned and capped before insert; session ids server-generated | **tested** (SQLite and PostgreSQL) |
| Disk fill / flooding | per-IP rate limit, body caps, retention purge and an event-count quota (newest kept), all adjustable at runtime with bounds | **tested** (limit, purge, quota, bounds); quota counts events, not bytes |
| Spoofed source IP | XFF trusted only from private proxy ranges; PROXY protocol only from trusted peers | **tested**; nginx stream config **syntax-verified** |
| Fake shell abuse | in-memory simulator; no subprocess/FS/network; forwarding/SFTP/SCP off; session and command limits | **tested** (limits not load-tested) |
| Prompt injection / false success claims | untrusted wrapping, schema validation, success-claim rejection, risk floor | **tested** with a fake provider; real LLM **not exercised** |
| Stored XSS in dashboard | React text rendering, no raw HTML | by design, no dedicated test |
| Control plane gets Docker access | not given: per-company containers are provisioned by a host-side CLI that only renders files and runs `docker compose` | rendering **tested**; the CLI itself **not run on Docker** |
| Admin token sniffed on the wire | optional TLS listener on 8443 | **verified** with real nginx and a certificate (self-signed) |
| Fake repos / traversal | repo files are dictionary lookups, never the filesystem | **tested** (`../../etc/passwd` returns 404) |
| Secrets in logs | JSON logs carry only session, IP, method, path, label, env | **tested** (a captured password never appears) |
| Emergency stop | `/admin/kill` returns 503 and refuses SSH logins | **tested**; audit log is in-memory only |

**Open issues / honest limitations**
- A decoy compromise can still insert fake events and publish to Redis (poisoning the feed). This is inherent: the decoy is the source of truth for events, so signing would not help (it would hold the key). Mitigations are the per-IP rate limit and the quota. It cannot read stored data or reach the admin token or LLM key.
- Admin token travels over plain HTTP; add TLS before exposing anything.
- A private-LAN attacker passes the admin allowlist. The Docker Desktop NAT hides real client IPs on a laptop.
- Captured SSH passwords are stored in plaintext; protect the database.
- Verified by 17 automated checks on one machine (Docker Desktop on Windows). Re-run `scripts/verify_stack.ps1` after any change and on your target host (Linux behaves differently for client IPs).
- Legal/ethics: deploy only on infrastructure you own and check local law and provider terms.
