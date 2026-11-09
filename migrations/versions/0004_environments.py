"""environments table + events.env column + grants for existing roles"""
revision = "0004"
down_revision = "0003"
from alembic import op
import sqlalchemy as sa

def upgrade() -> None:
    op.add_column("events", sa.Column("env", sa.String(64), nullable=False, server_default=""))
    op.create_table("environments", sa.Column("id", sa.String(32), primary_key=True), sa.Column("name", sa.String(64), nullable=False),
        sa.Column("industry", sa.String(64), nullable=False), sa.Column("size", sa.Integer, nullable=False), sa.Column("port", sa.Integer),
        sa.Column("status", sa.String(16), nullable=False, server_default="running"), sa.Column("created_at", sa.Float, nullable=False))
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DO $$ BEGIN "
                   "IF EXISTS (SELECT FROM pg_roles WHERE rolname='hiab_ingest') THEN GRANT SELECT ON environments TO hiab_ingest; END IF; "
                   "IF EXISTS (SELECT FROM pg_roles WHERE rolname='hiab_control') THEN GRANT SELECT, INSERT, UPDATE, DELETE ON environments TO hiab_control; END IF; END $$")

def downgrade() -> None:
    op.drop_table("environments"); op.drop_column("events", "env")
