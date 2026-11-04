"""Reusable model mixins shared across the data model.

- ``UUIDPrimaryKey`` — a UUID ``id`` primary key, generated server-side by
  Postgres (``gen_random_uuid()``) so the database owns identity even for rows
  inserted outside the ORM.
- ``TimestampMixin`` — a ``created_at`` column set server-side on insert.
"""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy import DateTime, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column


class UUIDPrimaryKey:
    """Mixin adding a server-generated UUID primary key named ``id``."""

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )


class TimestampMixin:
    """Mixin adding a server-set ``created_at`` timestamp."""

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
