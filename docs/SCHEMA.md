# Database schema (Alembic migrations in `migrations/versions`)
```mermaid
erDiagram
  events { int id PK
    float ts "epoch seconds"
    string session "12 hex chars, server-generated"
    string ip "real client IP (X-Forwarded-For / PROXY protocol from trusted proxies only)"
    string method "HTTP verb, SSH, or SSH-AUTH"
    text path
    text ua
    text body
    string label "classifier output"
    string env "environment that served it" }
  investigations { string session PK
    int n_events "events covered; stale when events grow"
    string source "llm | deterministic"
    text payload "Investigation JSON"
    float created_at }
  environments { string id PK "slug"
    string name
    string industry
    int size
    int port "8100-8119 when provisioned"
    string status "running | stopped"
    float created_at }
  settings { string key PK "company, killed"
    text value }
  audit { int id PK
    float ts
    text action }
  environments ||--o{ events : serves
  events ||--o| investigations : "analysed by analyst service"
```
Indexes: `ix_events_session`, `ix_events_ts`. Retention and quota are runtime settings (Settings page): events older than `retention_days` (default 30) are deleted and only the newest `max_events` (default 1,000,000) are kept, hourly and on demand. Attacker-controlled text is stripped of NUL bytes and length-capped before insert.
PostgreSQL roles (created by migrations 0002/0003 when the matching `HIAB_*_DB_PASSWORD` is set):

| Role | Used by | events | investigations | settings | audit |
|---|---|---|---|---|---|
| `hiab` (owner) | `migrate` job only | all | all | all | all |
| `hiab_ingest` | decoy | INSERT only | none | SELECT (also SELECT on `environments`) | none |
| `hiab_control` | control plane | SELECT, DELETE | SELECT | SELECT, INSERT, UPDATE (full CRUD on `environments`) | SELECT, INSERT |
| `hiab_analyst` | analyst service | SELECT | SELECT, INSERT, UPDATE | none | none |
