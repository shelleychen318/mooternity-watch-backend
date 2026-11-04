"""Database connectivity test.

Skips automatically when no database is reachable (e.g. CI without a Postgres
service), so the suite stays green in environments without the compose stack.
"""

from sqlalchemy.exc import OperationalError

from app.db import check_connection, get_session


def test_connectivity_or_skip():
    import pytest

    try:
        assert check_connection() is True
    except OperationalError:
        pytest.skip("No database reachable; connectivity test skipped.")


def test_session_dependency_yields_and_closes():
    import pytest

    gen = get_session()
    session = next(gen)
    try:
        assert session is not None
    except OperationalError:
        pytest.skip("No database reachable.")
    finally:
        gen.close()
