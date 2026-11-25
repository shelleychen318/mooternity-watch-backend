"""Smoke tests for app import and the /health endpoint."""

from fastapi.testclient import TestClient

from app.config import Environment, Settings
from app.main import app, create_app

client = TestClient(app)


def test_health_returns_200():
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "version" in body
    # database may be "ok" or "unavailable" depending on whether Postgres is up;
    # the endpoint must stay live either way.
    assert body["database"] in {"ok", "unavailable"}


def test_health_reports_environment_and_stays_live_without_db(monkeypatch):
    """/health stays live and reports the environment when the DB is unreachable.

    Liveness must not depend on the database: with the DB probe failing, the
    endpoint still returns 200 and reports ``database: "unavailable"`` rather
    than erroring, so an orchestrator does not restart a healthy process over a
    transient DB outage.
    """
    staging = Settings(environment=Environment.STAGING, auth_secret="a-real-secret")
    monkeypatch.setattr("app.main.get_settings", lambda: staging)
    # Force the DB probe to fail so we exercise the degraded-but-live path.
    monkeypatch.setattr(
        "app.main.check_connection",
        lambda: (_ for _ in ()).throw(RuntimeError("db down")),
    )

    resp = TestClient(create_app()).get("/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["environment"] == "staging"
    assert body["database"] == "unavailable"
