import pytest

@pytest.fixture(autouse=True)
def _isolated(monkeypatch, tmp_path):
    """Each test: no ambient secrets/services, a fresh SQLite DB, and reset in-memory state."""
    for v in ("HIAB_ADMIN_TOKEN", "ANTHROPIC_API_KEY", "DATABASE_URL", "REDIS_URL", "HIAB_GEOIP_DB", "HIAB_SKIP_MIGRATE", "HIAB_RATE_PER_MIN", "HIAB_SSH_PORT"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("HIAB_STATE_TTL", "0")
    monkeypatch.setenv("HIAB_DB", str(tmp_path / "events.db"))
    from app import bus, db, sshpot
    from app import runtime
    runtime.reset(); bus.reset(); sshpot.reset_state()
    yield
    db.dispose_all()
