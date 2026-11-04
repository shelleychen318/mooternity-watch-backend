"""Farm model.

A farm is the top-level tenant. Devices, users, events, and alerts are all
scoped to a farm.
"""

from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import TimestampMixin, UUIDPrimaryKey


class Farm(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "farms"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
