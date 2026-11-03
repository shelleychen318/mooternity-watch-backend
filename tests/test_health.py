"""Smoke tests for app import and the /health endpoint (M0-T1)."""

from fastapi.testclient import TestClient

from app.main import app

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
