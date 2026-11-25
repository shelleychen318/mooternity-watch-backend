"""Event ingestion endpoint.

``POST /v1/events`` validates an event against the versioned schema, persists it
as a single ``events`` row, and dedupes retries by ``event_id``.
"""

from __future__ import annotations

import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentDevice, DbSession
from app.models import Device, Event
from app.schemas.event import EventPayload
from app.schemas.version import UnsupportedSchemaVersionError, parse_event

router = APIRouter(prefix="/v1/events", tags=["events"])


class CreateEventResponse(BaseModel):
    event_id: str
    received_timestamp: datetime.datetime


def _to_event(payload: EventPayload, device: Device) -> Event:
    """Map the validated wire payload to an ``Event`` ORM row."""
    return Event(
        event_id=payload.event_id,
        farm_id=device.farm_id,
        device_id=device.id,
        event_type=payload.event_type.value,
        confidence=payload.confidence,
        detections=[d.model_dump(mode="json") for d in payload.detections],
        snapshot=payload.snapshot.model_dump(mode="json") if payload.snapshot else None,
        meta=payload.metadata,
        event_timestamp=payload.event_timestamp,
        received_timestamp=datetime.datetime.now(datetime.UTC),
    )


@router.post("", response_model=CreateEventResponse, status_code=201)
def create_event(
    device: CurrentDevice,
    session: DbSession,
    raw: Annotated[Any, Body()],
) -> CreateEventResponse:
    """Validate, persist (idempotently), and acknowledge an edge-device event."""
    try:
        payload = parse_event(raw)
    except UnsupportedSchemaVersionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors(include_url=False)) from exc

    event = _to_event(payload, device)
    session.add(event)
    try:
        session.commit()
    except IntegrityError:
        # Unique violation on ``event_id`` — a retried push. Roll back and
        # return the originally-stored row so retries are a no-op success.
        session.rollback()
        existing = session.scalar(select(Event).where(Event.event_id == payload.event_id))
        if existing is None:
            # The violation was not the expected dedupe case; surface it.
            raise
        return CreateEventResponse(
            event_id=existing.event_id,
            received_timestamp=existing.received_timestamp,
        )

    return CreateEventResponse(
        event_id=event.event_id,
        received_timestamp=event.received_timestamp,
    )
