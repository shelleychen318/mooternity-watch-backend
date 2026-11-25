"""Request-scoped API dependencies.

Authenticates an edge device from an ``Authorization: Bearer <device_key>``
header, matching against ``devices.device_key``. The authenticated device
carries the ``farm_id`` that scopes downstream requests.
"""

from __future__ import annotations

import datetime
import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Device

# auto_error=False so we normalize every failure (missing, malformed, unknown)
# to a single 401 below, rather than letting HTTPBearer raise its own 403.
_bearer_scheme = HTTPBearer(auto_error=False, description="Per-device credential")

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid or missing device credential.",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_device(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
    session: Annotated[Session, Depends(get_session)],
) -> Device:
    """Resolve the bearer token to a ``Device`` and stamp ``last_seen_at``.

    Any failure (no header, wrong scheme, unknown key) yields 401.
    """
    if credentials is None or not credentials.credentials:
        raise _UNAUTHORIZED

    presented = credentials.credentials

    device = session.scalar(select(Device).where(Device.device_key == presented))
    if device is None:
        raise _UNAUTHORIZED

    # Constant-time compare to avoid a timing side-channel on the key bytes.
    if not secrets.compare_digest(device.device_key, presented):
        raise _UNAUTHORIZED

    device.last_seen_at = datetime.datetime.now(datetime.UTC)
    session.add(device)
    session.commit()

    return device


CurrentDevice = Annotated[Device, Depends(get_current_device)]
DbSession = Annotated[Session, Depends(get_session)]
