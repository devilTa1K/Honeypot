"""settings + audit tables; least-privilege roles for the decoy (insert-only) and control plane (PostgreSQL only, when passwords are set)"""
revision = "0003"
down_revision = "0002"
import os, re
from alembic import op
import sqlalchemy as sa

def _role(name: str, env: str) -> bool:
    pw = os.environ.get(env)
    if not pw or op.get_bind().dialect.name != "postgresql": return False
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,64}", pw): raise RuntimeError(f"{env} must be 8-64 chars of [A-Za-z0-9_-]")
    op.execute(f"DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='{name}') THEN CREATE ROLE {name} LOGIN PASSWORD '{pw}'; END IF; END $$")
    return True

def upgrade() -> None:
    op.create_table("settings", sa.Column("key", sa.String(64), primary_key=True), sa.Column("value", sa.Text, nullable=False))
    op.create_table("audit", sa.Column("id", sa.Integer, primary_key=True, autoincrement=True), sa.Column("ts", sa.Float, nullable=False), sa.Column("action", sa.Text, nullable=False))
    if _role("hiab_ingest", "HIAB_INGEST_DB_PASSWORD"):      # decoy: can add events and read settings; cannot read events
        op.execute("GRANT INSERT ON events TO hiab_ingest"); op.execute("GRANT USAGE, SELECT ON SEQUENCE events_id_seq TO hiab_ingest")
        op.execute("GRANT SELECT ON settings TO hiab_ingest")
    if _role("hiab_control", "HIAB_CONTROL_DB_PASSWORD"):    # control plane: reads events, manages settings/audit; cannot insert events
        op.execute("GRANT SELECT, DELETE ON events TO hiab_control"); op.execute("GRANT SELECT ON investigations TO hiab_control")
        op.execute("GRANT SELECT, INSERT, UPDATE ON settings TO hiab_control"); op.execute("GRANT SELECT, INSERT ON audit TO hiab_control")
        op.execute("GRANT USAGE, SELECT ON SEQUENCE audit_id_seq TO hiab_control")

def downgrade() -> None:
    op.drop_table("audit"); op.drop_table("settings")
