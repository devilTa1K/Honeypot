"""investigations table + least-privilege analyst role (PostgreSQL only, when HIAB_ANALYST_DB_PASSWORD is set)"""
revision = "0002"
down_revision = "0001"
import os, re
from alembic import op
import sqlalchemy as sa

def upgrade() -> None:
    op.create_table("investigations", sa.Column("session", sa.String(32), primary_key=True), sa.Column("n_events", sa.Integer, nullable=False),
        sa.Column("source", sa.String(16), nullable=False), sa.Column("payload", sa.Text, nullable=False), sa.Column("created_at", sa.Float, nullable=False))
    pw = os.environ.get("HIAB_ANALYST_DB_PASSWORD")
    if pw and op.get_bind().dialect.name == "postgresql":
        if not re.fullmatch(r"[A-Za-z0-9_-]{8,64}", pw):
            raise RuntimeError("HIAB_ANALYST_DB_PASSWORD must be 8-64 chars of [A-Za-z0-9_-]")
        op.execute(f"DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='hiab_analyst') THEN CREATE ROLE hiab_analyst LOGIN PASSWORD '{pw}'; END IF; END $$")
        op.execute("GRANT SELECT ON events TO hiab_analyst")
        op.execute("GRANT SELECT, INSERT, UPDATE ON investigations TO hiab_analyst")

def downgrade() -> None:
    op.drop_table("investigations")
