from alembic import context
from sqlalchemy import create_engine
from app.db import database_url, metadata

url = context.config.get_main_option("sqlalchemy.url") or database_url()
eng = create_engine(url)
with eng.connect() as conn:
    context.configure(connection=conn, target_metadata=metadata)
    with context.begin_transaction():
        context.run_migrations()
eng.dispose()
