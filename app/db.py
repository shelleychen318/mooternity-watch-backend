"""Database engine, session management, and the ORM declarative base.

Exposes:
- ``engine`` / ``SessionLocal`` for SQLAlchemy access.
- ``Base`` — the declarative base that all models inherit from.
- ``get_session`` — a FastAPI dependency yielding a request-scoped session.
- ``check_connection`` — a lightweight connectivity probe used by tests and
  the ``/health`` endpoint.
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


_settings = get_settings()

engine = create_engine(
    str(_settings.database_url),
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """Yield a request-scoped SQLAlchemy session (FastAPI dependency)."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def check_connection() -> bool:
    """Return True if a trivial query against the database succeeds."""
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return True
