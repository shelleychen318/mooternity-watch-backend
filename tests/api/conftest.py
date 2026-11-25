"""A TestClient wired to the test database's transaction.

Handlers commit (device auth stamps ``last_seen_at``), so the session is joined
to the fixture's outer transaction with a SAVEPOINT that restarts on each commit
— keeping per-test isolation while letting the handler commit as in production
(SQLAlchemy's "join an external transaction" recipe).
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.db import get_session
from app.main import create_app


@pytest.fixture
def client(db_session: Session) -> Iterator[TestClient]:
    """TestClient whose ``get_session`` yields the test's transaction session.

    Via ``db_session``, skips when no test database is reachable.
    """
    db_session.connection().begin_nested()

    @event.listens_for(db_session, "after_transaction_end")
    def _restart_savepoint(session: Session, transaction) -> None:
        if transaction.nested and not transaction._parent.nested:
            session.begin_nested()

    def _override_get_session() -> Iterator[Session]:
        yield db_session

    app = create_app()
    app.dependency_overrides[get_session] = _override_get_session

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        event.remove(db_session, "after_transaction_end", _restart_savepoint)
        app.dependency_overrides.clear()
