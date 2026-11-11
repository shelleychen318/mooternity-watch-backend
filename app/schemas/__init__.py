from __future__ import annotations

from app.schemas.classification import (
    DEFAULT_HANDLING_PATH,
    HandlingPath,
    classify,
)
from app.schemas.event import (
    BoundingBox,
    Detection,
    EventPayload,
    EventType,
    Snapshot,
)
from app.schemas.version import (
    SUPPORTED_MAJOR_VERSIONS,
    UnsupportedSchemaVersionError,
    check_schema_version,
    parse_event,
)

__all__ = [
    "DEFAULT_HANDLING_PATH",
    "SUPPORTED_MAJOR_VERSIONS",
    "BoundingBox",
    "Detection",
    "EventPayload",
    "EventType",
    "HandlingPath",
    "Snapshot",
    "UnsupportedSchemaVersionError",
    "check_schema_version",
    "classify",
    "parse_event",
]
