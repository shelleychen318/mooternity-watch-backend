"""Tests for the schema versioning strategy."""

from __future__ import annotations

import copy

import pytest

from app.schemas import (
    EventType,
    UnsupportedSchemaVersionError,
    check_schema_version,
    parse_event,
)
from tests.schemas.test_event import DESIGN_EXAMPLE_PAYLOAD


@pytest.mark.parametrize("version", ["1.0", "1.5", "1.7", "1.42"])
def test_known_major_any_minor_is_accepted(version):
    # Does not raise.
    check_schema_version(version)


def test_unsupported_major_is_rejected_with_actionable_message():
    with pytest.raises(UnsupportedSchemaVersionError) as exc:
        check_schema_version("2.0")

    message = str(exc.value)
    assert "2.0" in message  # names the received version
    assert "1" in message  # names the supported major(s)


def test_malformed_version_is_rejected():
    with pytest.raises(UnsupportedSchemaVersionError):
        check_schema_version("abc")


def test_parse_event_accepts_known_version_and_returns_payload():
    event = parse_event(DESIGN_EXAMPLE_PAYLOAD)
    assert event.event_type is EventType.CALVING_DETECTED


def test_parse_event_rejects_unsupported_major_before_validation():
    payload = copy.deepcopy(DESIGN_EXAMPLE_PAYLOAD)
    payload["schema_version"] = "2.0"
    with pytest.raises(UnsupportedSchemaVersionError):
        parse_event(payload)


def test_parse_event_requires_schema_version():
    payload = copy.deepcopy(DESIGN_EXAMPLE_PAYLOAD)
    del payload["schema_version"]
    with pytest.raises(UnsupportedSchemaVersionError):
        parse_event(payload)
