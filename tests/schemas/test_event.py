"""Tests for the event payload contract.
"""

from __future__ import annotations

import copy

import pytest
from pydantic import ValidationError

from app.schemas import BoundingBox, Detection, EventPayload, EventType, Snapshot

DESIGN_EXAMPLE_PAYLOAD = {
    "event_id": "evt_01HTX9P5N8K2J7QF3R4W6YABCD",
    "schema_version": "1.0",
    "device_id": "dev_barn01_pi5",
    "farm_id": "farm_demo_001",
    "event_type": "calving_detected",
    "event_timestamp": "2026-02-14T03:21:47.123Z",
    "received_timestamp": None,
    "confidence": 0.92,
    "snapshot": {
        "url": "https://store.com/farm_demo_001/cam_pen_03/evt_01HTX9.jpg",
        "width": 1920,
        "height": 1080,
        "format": "jpeg",
        "captured_at": "2026-02-14T03:21:47.100Z",
    },
    "detections": [
        {
            "label": "calving",
            "confidence": 0.95,
            "bbox": {"x": 0.34, "y": 0.21, "width": 0.28, "height": 0.41},
        }
    ],
    "metadata": {"model_version": "calving-detector-v2.3"},
}


def test_event_type_enum_covers_known_set():
    assert {e.value for e in EventType} == {
        "calving_detected",
        "cow_detected",
        "camera_offline",
        "error",
    }


def test_design_example_payload_parses():
    event = EventPayload.model_validate(DESIGN_EXAMPLE_PAYLOAD)

    assert event.event_id == "evt_01HTX9P5N8K2J7QF3R4W6YABCD"
    assert event.event_type is EventType.CALVING_DETECTED
    assert event.received_timestamp is None
    assert event.confidence == 0.92
    assert event.snapshot is not None
    assert event.snapshot.width == 1920
    assert event.snapshot.format == "jpeg"
    assert len(event.detections) == 1
    assert event.detections[0].label == "calving"
    assert event.detections[0].bbox.width == 0.28
    assert event.metadata == {"model_version": "calving-detector-v2.3"}


@pytest.mark.parametrize("missing_field", ["event_id", "event_type", "event_timestamp"])
def test_missing_required_field_is_rejected(missing_field):
    payload = copy.deepcopy(DESIGN_EXAMPLE_PAYLOAD)
    del payload[missing_field]

    with pytest.raises(ValidationError) as exc:
        EventPayload.model_validate(payload)

    # The error names the offending field, so the message is actionable.
    assert missing_field in str(exc.value)


def test_unknown_event_type_is_rejected():
    payload = copy.deepcopy(DESIGN_EXAMPLE_PAYLOAD)
    payload["event_type"] = "aliens_detected"

    with pytest.raises(ValidationError) as exc:
        EventPayload.model_validate(payload)

    assert "event_type" in str(exc.value)


def test_minimal_payload_defaults_optional_fields():
    payload = {
        "event_id": "evt_minimal",
        "schema_version": "1.0",
        "device_id": "dev_barn01_pi5",
        "farm_id": "farm_demo_001",
        "event_type": "cow_detected",
        "event_timestamp": "2026-02-14T03:21:47.123Z",
    }

    event = EventPayload.model_validate(payload)

    assert event.received_timestamp is None
    assert event.confidence is None
    assert event.snapshot is None
    assert event.detections == []
    assert event.metadata == {}


def test_extra_fields_are_ignored_for_forward_compat():
    payload = copy.deepcopy(DESIGN_EXAMPLE_PAYLOAD)
    payload["some_future_field"] = "from a newer minor version"

    event = EventPayload.model_validate(payload)

    assert not hasattr(event, "some_future_field")


# --- Nested model constraints ---------------------------


def test_bounding_box_rejects_out_of_range():
    with pytest.raises(ValidationError):
        BoundingBox(x=1.5, y=0.1, width=0.2, height=0.2)


def test_detection_rejects_confidence_out_of_range():
    with pytest.raises(ValidationError):
        Detection(
            label="calving",
            confidence=1.4,
            bbox=BoundingBox(x=0.1, y=0.1, width=0.2, height=0.2),
        )


def test_detection_requires_bbox():
    with pytest.raises(ValidationError) as exc:
        Detection.model_validate({"label": "calving", "confidence": 0.9})
    assert "bbox" in str(exc.value)


def test_snapshot_rejects_non_positive_dimensions():
    with pytest.raises(ValidationError):
        Snapshot.model_validate(
            {
                "url": "https://store.com/x.jpg",
                "width": 0,
                "height": 1080,
                "format": "jpeg",
                "captured_at": "2026-02-14T03:21:47.100Z",
            }
        )


def test_confidence_out_of_range_on_payload_is_rejected():
    payload = copy.deepcopy(DESIGN_EXAMPLE_PAYLOAD)
    payload["confidence"] = 1.2
    with pytest.raises(ValidationError):
        EventPayload.model_validate(payload)
