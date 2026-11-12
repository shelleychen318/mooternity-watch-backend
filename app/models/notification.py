"""Notification model.

This table doubles as a job queue for the Notification Worker: rows are
inserted as ``pending`` by the Alert Engine, then a background worker polls for
due rows, dispatches them, and transitions each to ``sent`` or ``failed``.

- ``channel`` / ``status`` are DB-native enums for integrity.
- ``attempts``, ``next_retry_at``, ``last_error`` support retry-with-backoff.
- A composite index on ``(status, next_retry_at)`` makes polling for due
  ``pending`` rows efficient.
"""

from __future__ import annotations

import datetime
import enum
import uuid

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import TimestampMixin, UUIDPrimaryKey


class NotificationChannel(enum.StrEnum):
    SMS = "sms"
    PUSH = "push"
    EMAIL = "email"


class NotificationStatus(enum.StrEnum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class Notification(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "notifications"

    alert_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("alerts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    channel: Mapped[NotificationChannel] = mapped_column(
        Enum(
            NotificationChannel,
            name="notification_channel",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
    )
    status: Mapped[NotificationStatus] = mapped_column(
        Enum(
            NotificationStatus,
            name="notification_status",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=NotificationStatus.PENDING,
    )

    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_retry_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_error: Mapped[str | None] = mapped_column(String, nullable=True)
    sent_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        # Supports the worker's "find due pending rows" poll.
        Index("ix_notifications_status_next_retry_at", "status", "next_retry_at"),
    )
