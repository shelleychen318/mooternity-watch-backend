"""Device model.

An edge device belonging to a farm. ``device_key`` is the per-device credential
string used to authenticate ingestion requests. ``last_seen_at`` tracks the
most recent contact for operational monitoring.
"""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import TimestampMixin, UUIDPrimaryKey


class Device(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "devices"

    farm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("farms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    device_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    last_seen_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
