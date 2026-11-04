from __future__ import annotations

import datetime
import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Alert, AlertStatus
from tests.conftest import make_event, make_farm


def test_alert_lifecycle_transitions(db_session: Session):
    event = make_event(db_session)

    alert = Alert(farm_id=event.farm_id, event_id=event.id)
    db_session.add(alert)
    db_session.flush()
    assert alert.status == AlertStatus.ACTIVE
    assert alert.acknowledged_at is None
    assert alert.resolved_at is None

    alert.status = AlertStatus.ACKNOWLEDGED
    alert.acknowledged_at = datetime.datetime.now(datetime.UTC)
    db_session.flush()
    db_session.expire(alert)
    fetched = db_session.get(Alert, alert.id)
    assert fetched.status == AlertStatus.ACKNOWLEDGED
    assert fetched.acknowledged_at is not None

    alert.status = AlertStatus.RESOLVED
    alert.resolved_at = datetime.datetime.now(datetime.UTC)
    db_session.flush()
    db_session.expire(alert)
    fetched = db_session.get(Alert, alert.id)
    assert fetched.status == AlertStatus.RESOLVED
    assert fetched.resolved_at is not None


def test_alert_requires_valid_event_fk(db_session: Session):
    farm = make_farm(db_session)

    alert = Alert(farm_id=farm.id, event_id=uuid.uuid4())
    db_session.add(alert)
    with pytest.raises(IntegrityError):
        db_session.flush()
