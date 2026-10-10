from alembic import context
from sqlalchemy import create_engine

from app import models  # noqa: F401  (registers tables)
from app.config import get_settings
from app.db.base import Base

target_metadata = Base.metadata


def run_migrations_online() -> None:
    engine = create_engine(get_settings().database_migrator_url)
    with engine.connect() as conn:
        context.configure(connection=conn, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
