"""Snapshot upload-URL endpoint.

Mints a short-lived presigned ``PUT`` URL for an authenticated device. The key
is derived server-side from the device's ``farm_id``, so a device can only write
under its own farm's prefix.
"""

from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import CurrentDevice
from app.config import Settings, get_settings
from app.storage.signing import generate_presigned_put_url

router = APIRouter(prefix="/v1/snapshots", tags=["snapshots"])

# Event ids compose into the object key; constrain to key-safe characters.
# Rejecting slashes stops a device smuggling a path traversal into its key.
_EVENT_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


class UploadUrlRequest(BaseModel):
    event_id: str = Field(min_length=1, max_length=128)


class UploadUrlResponse(BaseModel):
    upload_url: str
    key: str
    ttl_seconds: int


def _snapshot_key(farm_id: str, event_id: str, *, settings: Settings) -> str:
    return f"{settings.s3_snapshot_prefix}{farm_id}/{event_id}.jpg"


@router.post("/upload-url", response_model=UploadUrlResponse)
def create_upload_url(
    body: UploadUrlRequest,
    device: CurrentDevice,
) -> UploadUrlResponse:
    """Mint a presigned PUT URL scoped to the authenticated device's farm."""
    settings = get_settings()

    if not _EVENT_ID_PATTERN.match(body.event_id):
        raise HTTPException(
            status_code=422,
            detail="event_id must be 1-128 chars of letters, digits, '.', '_' or '-'.",
        )

    key = _snapshot_key(str(device.farm_id), body.event_id, settings=settings)
    signed = generate_presigned_put_url(key, settings=settings)

    return UploadUrlResponse(
        upload_url=signed.url,
        key=key,
        ttl_seconds=signed.ttl_seconds,
    )
