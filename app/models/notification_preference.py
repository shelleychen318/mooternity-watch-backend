"""NotificationPreference model.

A user's per-channel notification settings plus optional quiet hours. The FK to
``users`` carries a **unique constraint**, enforcing a one-to-one relationship:
each user has at most one preferences row. Channel flags default to enabled so a
newly created user has sensible defaults.
"""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy import Boolean, ForeignKey, Time
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import TimestampMixin, UUIDPrimaryKey


class NotificationPreference(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "notification_preferences"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # one-to-one with users
    )

    sms_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    push_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    email_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    quiet_hours_start: Mapped[datetime.time | None] = mapped_column(Time, nullable=True)
    quiet_hours_end: Mapped[datetime.time | None] = mapped_column(Time, nullable=True)
