"""Device-authentication dependency, exercised via the upload-URL endpoint."""

from __future__ import annotations

import logging

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.conftest import make_device

UPLOAD_URL_PATH = "/v1/snapshots/upload-url"
VALID_KEY = "dev_seeded_key_for_tests"


def _request(client: TestClient, *, auth: str | None) -> object:
    headers = {"Authorization": auth} if auth is not None else {}
    return client.post(UPLOAD_URL_PATH, json={"event_id": "evt_auth_001"}, headers=headers)


def test_valid_credential_is_accepted(client: TestClient, db_session: Session) -> None:
    make_device(db_session, device_key=VALID_KEY)

    resp = _request(client, auth=f"Bearer {VALID_KEY}")

    assert resp.status_code == 200


def test_unknown_credential_is_rejected(client: TestClient, db_session: Session) -> None:
    make_device(db_session, device_key=VALID_KEY)

    resp = _request(client, auth="Bearer not-the-right-key")

    assert resp.status_code == 401


def test_missing_credential_is_rejected(client: TestClient, db_session: Session) -> None:
    make_device(db_session, device_key=VALID_KEY)

    resp = _request(client, auth=None)

    assert resp.status_code == 401


def test_wrong_scheme_is_rejected(client: TestClient, db_session: Session) -> None:
    make_device(db_session, device_key=VALID_KEY)

    # Non-Bearer scheme rejected even though the value is a valid key.
    resp = _request(client, auth=f"Basic {VALID_KEY}")

    assert resp.status_code == 401


def test_successful_auth_stamps_last_seen_at(client: TestClient, db_session: Session) -> None:
    device = make_device(db_session, device_key=VALID_KEY)
    assert device.last_seen_at is None

    resp = _request(client, auth=f"Bearer {VALID_KEY}")
    assert resp.status_code == 200

    db_session.refresh(device)
    assert device.last_seen_at is not None


def test_credential_is_never_logged(client: TestClient, db_session: Session, caplog) -> None:
    make_device(db_session, device_key=VALID_KEY)

    with caplog.at_level(logging.DEBUG):
        _request(client, auth=f"Bearer {VALID_KEY}")
        _request(client, auth="Bearer wrong-key-value")

    for record in caplog.records:
        assert VALID_KEY not in record.getMessage()
        assert "wrong-key-value" not in record.getMessage()
