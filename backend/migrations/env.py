"""Alembic environment — wired to the app's SQLModel metadata + DATABASE_URL."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

from app import config as app_config
from app import models  # noqa: F401  (import registers all tables on the metadata)

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)

# Always take the URL from the app config (env-driven), not alembic.ini.
config.set_main_option("sqlalchemy.url", app_config.DATABASE_URL)
target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    context.configure(url=app_config.DATABASE_URL, target_metadata=target_metadata,
                      literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
