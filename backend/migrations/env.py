"""Alembic environment — wired to the app's SQLModel metadata + DATABASE_URL."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool
from sqlmodel import SQLModel

from app import config as app_config
from app import models  # noqa: F401  (import registers all tables on the metadata)

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)

# Build engines straight from the app's DATABASE_URL (env-driven). We deliberately
# do NOT route it through alembic.ini's configparser, whose %-interpolation would
# choke on percent-encoded passwords (e.g. %21 for '!').
target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    context.configure(url=app_config.DATABASE_URL, target_metadata=target_metadata,
                      literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(app_config.DATABASE_URL, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
