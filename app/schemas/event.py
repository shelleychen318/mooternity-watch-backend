"""Pydantic models for the event payload pushed to the ingestion API.

Field names mirror the JSON keys exactly.
"""

from __future__ import annotations

import datetime
import enum

from pydantic import BaseModel, ConfigDict, Field


class EventType(enum.StrEnum):
    """Known event types. Unknown values fail validation."""

    CALVING_DETECTED = "calving_detected"
    COW_DETECTED = "cow_detected"
    CAMERA_OFFLINE = "camera_offline"
    ERROR = "error"


class BoundingBox(BaseModel):
    """Bounding box as fractions of the frame (0..1)."""

    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(ge=0, le=1)
    height: float = Field(ge=0, le=1)


class Detection(BaseModel):
    """A single detection with its bounding box."""

    label: str
    confidence: float = Field(ge=0, le=1)
    bbox: BoundingBox


class Snapshot(BaseModel):
    """Reference to a snapshot image (URL + metadata)."""

    url: str
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    format: str
    captured_at: datetime.datetime


class EventPayload(BaseModel):
    """Top-level event payload. Unknown fields are ignored."""

    model_config = ConfigDict(extra="ignore")

    event_id: str
    schema_version: str
    device_id: str
    farm_id: str
    event_type: EventType
    event_timestamp: datetime.datetime
    # Null on the wire; stamped server-side on ingestion.
    received_timestamp: datetime.datetime | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    snapshot: Snapshot | None = None
    detections: list[Detection] = Field(default_factory=list)
    # Free-form bag for extra fields.
    metadata: dict = Field(default_factory=dict)
