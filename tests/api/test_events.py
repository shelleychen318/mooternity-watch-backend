"""Event ingestion endpoint (``POST /v1/events``).

Covers schema validation + persistence, idempotent dedupe by ``event_id``, and
server-side receive-time stamping with out-of-order tolerance.
"""

from __future__ import annotations

import datetime
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Event
from tests.conftest import make_device

EVENTS_PATH = "/v1/events"
VALID_KEY = "dev_seeded_key_for_tests"


def _make_event_payload(**overrides: Any) -> dict[str, Any]:
    """Build a valid event payload; identity is derived from auth, not the body."""
    payload: dict[str, Any] = {
        "event_id": "evt_ingest_001",
        "schema_version": "1.0",
        "event_type": "calving_detected",
        "event_timestamp": "2026-11-25T10:00:00+00:00",
        "confidence": 0.91,
        "snapshot": {
            "url": "https://example.com/snap.jpg",
            "width": 1920,
            "height": 1080,
            "format": "jpeg",
            "captured_at": "2026-11-25T10:00:00+00:00",
        },
        "detections": [
            {
                "label": "cow",
                "confidence": 0.95,
                "bbox": {"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.4},
            }
        ],
        "metadata": {"model_version": "calving-detector-v2.3"},
    }
    payload.update(overrides)
    return payload


def _post(client: TestClient, payload: dict[str, Any], *, key: str = VALID_KEY) -> Any:
    return client.post(
        EVENTS_PATH,
        json=payload,
        headers={"Authorization": f"Bearer {key}"},
    )


def _count_events(session: Session, event_id: str) -> int:
    return session.scalar(select(func.count()).select_from(Event).where(Event.event_id == event_id))


def test_valid_payload_persists_one_row(client: TestClient, db_session: Session) -> None:
    device = make_device(db_session, device_key=VALID_KEY)
    payload = _make_event_payload()

    resp = _post(client, payload)

    assert resp.status_code == 201
    body = resp.json()
    assert body["event_id"] == payload["event_id"]
    assert body["received_timestamp"]

    row = db_session.scalar(select(Event).where(Event.event_id == payload["event_id"]))
    assert row is not None
    # Identity is derived server-side from the authenticated device, not the body.
    assert row.farm_id == device.farm_id
    assert row.device_id == device.id
    assert row.event_type == "calving_detected"
    assert row.meta == {"model_version": "calving-detector-v2.3"}
    assert _count_events(db_session, payload["event_id"]) == 1


def test_bad_event_type_is_rejected(client: TestClient, db_session: Session) -> None:
    make_device(db_session, device_key=VALID_KEY)
    payload = _make_event_payload(event_type="not_a_real_type")

    resp = _post(client, payload)

    assert resp.status_code == 422
    assert resp.json()["detail"]


def test_missing_required_field_is_rejected(client: TestClient, db_session: Session) -> None:
    make_device(db_session, device_key=VALID_KEY)
    payload = _make_event_payload()
    del payload["event_timestamp"]

    resp = _post(client, payload)

    assert resp.status_code == 422


def test_unsupported_schema_version_is_rejected(client: TestClient, db_session: Session) -> None:
    make_device(db_session, device_key=VALID_KEY)
    payload = _make_event_payload(schema_version="2.0")

    resp = _post(client, payload)

    assert resp.status_code == 422


def test_malformed_schema_version_is_rejected(client: TestClient, db_session: Session) -> None:
    make_device(db_session, device_key=VALID_KEY)
    payload = _make_event_payload(schema_version="not-a-version")

    resp = _post(client, payload)

    assert resp.status_code == 422


def test_unauthenticated_is_rejected(client: TestClient, db_session: Session) -> None:
    make_device(db_session, device_key=VALID_KEY)
    payload = _make_event_payload()

    resp = client.post(EVENTS_PATH, json=payload)

    assert resp.status_code == 401


def test_reposting_same_event_id_is_a_noop_success(client: TestClient, db_session: Session) -> None:
    make_device(db_session, device_key=VALID_KEY)
    payload = _make_event_payload()

    first = _post(client, payload)
    second = _post(client, payload)

    assert first.status_code == 201
    assert second.status_code == 201
    assert _count_events(db_session, payload["event_id"]) == 1
    # A dedupe hit echoes the originally-stored receive time, not a re-stamp.
    assert second.json()["received_timestamp"] == first.json()["received_timestamp"]


def test_distinct_event_ids_create_distinct_rows(client: TestClient, db_session: Session) -> None:
    device = make_device(db_session, device_key=VALID_KEY)

    assert _post(client, _make_event_payload(event_id="evt_a")).status_code == 201
    assert _post(client, _make_event_payload(event_id="evt_b")).status_code == 201

    total = db_session.scalar(
        select(func.count()).select_from(Event).where(Event.device_id == device.id)
    )
    assert total == 2


def test_received_timestamp_is_server_stamped(client: TestClient, db_session: Session) -> None:
    make_device(db_session, device_key=VALID_KEY)
    before = datetime.datetime.now(datetime.UTC)
    # A bogus/old payload value must be ignored.
    payload = _make_event_payload(received_timestamp="2000-01-01T00:00:00+00:00")

    resp = _post(client, payload)
    after = datetime.datetime.now(datetime.UTC)

    assert resp.status_code == 201
    row = db_session.scalar(select(Event).where(Event.event_id == payload["event_id"]))
    assert row.received_timestamp is not None
    assert before <= row.received_timestamp <= after


def test_null_received_timestamp_is_server_stamped(client: TestClient, db_session: Session) -> None:
    make_device(db_session, device_key=VALID_KEY)
    payload = _make_event_payload(received_timestamp=None)

    resp = _post(client, payload)

    assert resp.status_code == 201
    row = db_session.scalar(select(Event).where(Event.event_id == payload["event_id"]))
    assert row.received_timestamp is not None


def test_out_of_order_events_persist_and_sort_by_receive_time(
    client: TestClient, db_session: Session
) -> None:
    device = make_device(db_session, device_key=VALID_KEY)
    # Posted first but with a *later* event_timestamp than the second.
    first = _make_event_payload(
        event_id="evt_late_clock", event_timestamp="2026-11-25T12:00:00+00:00"
    )
    second = _make_event_payload(
        event_id="evt_early_clock", event_timestamp="2026-11-25T08:00:00+00:00"
    )

    assert _post(client, first).status_code == 201
    assert _post(client, second).status_code == 201

    ordered = db_session.scalars(
        select(Event).where(Event.device_id == device.id).order_by(Event.received_timestamp)
    ).all()
    assert [e.event_id for e in ordered] == ["evt_late_clock", "evt_early_clock"]
