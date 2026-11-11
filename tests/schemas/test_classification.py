"""Tests for event-type classification.
"""

from __future__ import annotations

import app.schemas.classification as classification
from app.schemas import EventType, HandlingPath, classify


def test_known_types_map_to_their_documented_paths():
    assert classify(EventType.CALVING_DETECTED) is HandlingPath.ALERT_WORTHY
    assert classify(EventType.COW_DETECTED) is HandlingPath.LOG_ONLY
    assert classify(EventType.CAMERA_OFFLINE) is HandlingPath.OPERATIONAL
    assert classify(EventType.ERROR) is HandlingPath.OPERATIONAL


def test_every_known_type_classifies_to_a_valid_path():
    # Totality: the classifier returns a HandlingPath for every current type.
    for event_type in EventType:
        assert isinstance(classify(event_type), HandlingPath)


def test_unmapped_type_falls_back_to_log_only(monkeypatch):
    # Simulate a valid enum member that has not yet been given a handling path
    # (e.g. a new CV type added to the enum but not yet mapped). It must fall to
    # the documented safe default rather than raising.
    reduced_map = dict(classification._HANDLING_BY_TYPE)
    reduced_map.pop(EventType.COW_DETECTED)
    monkeypatch.setattr(classification, "_HANDLING_BY_TYPE", reduced_map)

    assert classify(EventType.COW_DETECTED) is HandlingPath.LOG_ONLY
    assert classification.DEFAULT_HANDLING_PATH is HandlingPath.LOG_ONLY
