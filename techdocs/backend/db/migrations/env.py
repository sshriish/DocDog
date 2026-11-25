from alembic import context
from sqlalchemy import text
from core.config import get_settings
from db.session import Base, engine
import db.models  # noqa: register tables

def run():
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
        context.configure(connection=conn, target_metadata=Base.metadata)
        with context.begin_transaction():
            context.run_migrations()
run()
