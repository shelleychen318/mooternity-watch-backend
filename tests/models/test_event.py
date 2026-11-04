from __future__ import annotations

import datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Event
from tests.conftest import make_device


def test_duplicate_event_id_raises_unique_violation(db_session: Session):
    device = make_device(db_session)

    db_session.add(
        Event(
            event_id="evt_dup",
            farm_id=device.farm_id,
            device_id=device.id,
            event_type="calving_detected",
        )
    )
    db_session.flush()

    db_session.add(
        Event(
            event_id="evt_dup",
            farm_id=device.farm_id,
            device_id=device.id,
            event_type="calving_detected",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_jsonb_nested_payload_round_trips(db_session: Session):
    device = make_device(db_session)

    detections = [
        {
            "label": "calving",
            "confidence": 0.95,
            "bbox": {"x": 0.34, "y": 0.21, "width": 0.28, "height": 0.41},
        }
    ]
    snapshot = {
        "url": "https://store.example/farm/cam/evt.jpg",
        "width": 1920,
        "height": 1080,
        "format": "jpeg",
    }
    meta = {"model_version": "calving-detector-v2.3", "extra": {"nested": [1, 2, 3]}}

    event = Event(
        event_id="evt_jsonb",
        farm_id=device.farm_id,
        device_id=device.id,
        event_type="calving_detected",
        confidence=0.92,
        detections=detections,
        snapshot=snapshot,
        meta=meta,
        event_timestamp=datetime.datetime(2026, 2, 14, 3, 21, 47, tzinfo=datetime.UTC),
    )
    db_session.add(event)
    db_session.flush()
    db_session.expire(event)  # force a fresh read from the DB

    fetched = db_session.get(Event, event.id)
    assert fetched is not None
    assert fetched.detections == detections
    assert fetched.snapshot == snapshot
    assert fetched.meta == meta
    assert fetched.detections[0]["bbox"]["width"] == 0.28
    assert fetched.meta["extra"]["nested"] == [1, 2, 3]
