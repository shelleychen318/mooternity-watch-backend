"""ORM models package.

Importing this package registers every model's table on ``Base.metadata``,
which is what Alembic's autogenerate and the test fixtures rely on. Each model
is defined in its own module and re-exported here.
"""

from __future__ import annotations

from app.db import Base
from app.models.alert import Alert, AlertStatus
from app.models.base import TimestampMixin, UUIDPrimaryKey
from app.models.device import Device
from app.models.event import Event
from app.models.farm import Farm
from app.models.notification import (
    Notification,
    NotificationChannel,
    NotificationStatus,
)
from app.models.notification_preference import NotificationPreference
from app.models.user import User

__all__ = [
    "Alert",
    "AlertStatus",
    "Base",
    "Device",
    "Event",
    "Farm",
    "Notification",
    "NotificationChannel",
    "NotificationPreference",
    "NotificationStatus",
    "TimestampMixin",
    "UUIDPrimaryKey",
    "User",
]
