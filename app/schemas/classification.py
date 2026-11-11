"""Map an ``event_type`` to the handling path it takes once persisted."""

from __future__ import annotations

import enum

from app.schemas.event import EventType


class HandlingPath(enum.StrEnum):
    ALERT_WORTHY = "alert_worthy"
    LOG_ONLY = "log_only"
    OPERATIONAL = "operational"


_HANDLING_BY_TYPE: dict[EventType, HandlingPath] = {
    EventType.CALVING_DETECTED: HandlingPath.ALERT_WORTHY,
    EventType.COW_DETECTED: HandlingPath.LOG_ONLY,
    EventType.CAMERA_OFFLINE: HandlingPath.OPERATIONAL,
    EventType.ERROR: HandlingPath.OPERATIONAL,
}

DEFAULT_HANDLING_PATH: HandlingPath = HandlingPath.LOG_ONLY


def classify(event_type: EventType) -> HandlingPath:
    """Return the handling path for an event type, defaulting to ``LOG_ONLY``."""
    return _HANDLING_BY_TYPE.get(event_type, DEFAULT_HANDLING_PATH)
