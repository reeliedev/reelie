"""Database engine + session helpers (SQLModel)."""

from __future__ import annotations

from collections.abc import Iterator

from sqlmodel import Session, SQLModel, create_engine

from app import config

_connect_args = {"check_same_thread": False} if config.DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(config.DATABASE_URL, echo=False, connect_args=_connect_args)


def init_db() -> None:
    # Import models so they're registered on SQLModel.metadata.
    from app import models  # noqa: F401
    # Dev convenience: auto-create tables on SQLite. In prod, Alembic owns the
    # schema (`alembic upgrade head` runs at deploy) — don't create_all there.
    if not config.IS_PROD:
        SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
