"""create events table"""
revision = "0001"
down_revision = None
from alembic import op
import sqlalchemy as sa

def upgrade() -> None:
    op.create_table("events", sa.Column("id", sa.Integer, primary_key=True, autoincrement=True), sa.Column("ts", sa.Float, nullable=False),
        sa.Column("session", sa.String(32), nullable=False), sa.Column("ip", sa.String(64), nullable=False), sa.Column("method", sa.String(16), nullable=False),
        sa.Column("path", sa.Text, nullable=False), sa.Column("ua", sa.Text, nullable=False), sa.Column("body", sa.Text, nullable=False), sa.Column("label", sa.String(40), nullable=False))
    op.create_index("ix_events_session", "events", ["session"])
    op.create_index("ix_events_ts", "events", ["ts"])

def downgrade() -> None:
    op.drop_table("events")
