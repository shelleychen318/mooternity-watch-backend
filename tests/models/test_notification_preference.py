from __future__ import annotations

import datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import NotificationPreference
from tests.conftest import make_user


def test_defaults_for_new_user(db_session: Session):
    user = make_user(db_session)

    prefs = NotificationPreference(user_id=user.id)
    db_session.add(prefs)
    db_session.flush()
    db_session.expire(prefs)

    fetched = db_session.get(NotificationPreference, prefs.id)
    assert fetched.sms_enabled is True
    assert fetched.push_enabled is True
    assert fetched.email_enabled is False
    assert fetched.quiet_hours_start is None
    assert fetched.quiet_hours_end is None


def test_quiet_hours_round_trip(db_session: Session):
    user = make_user(db_session)

    prefs = NotificationPreference(
        user_id=user.id,
        quiet_hours_start=datetime.time(22, 0),
        quiet_hours_end=datetime.time(6, 30),
    )
    db_session.add(prefs)
    db_session.flush()
    db_session.expire(prefs)

    fetched = db_session.get(NotificationPreference, prefs.id)
    assert fetched.quiet_hours_start == datetime.time(22, 0)
    assert fetched.quiet_hours_end == datetime.time(6, 30)


def test_one_to_one_enforced(db_session: Session):
    user = make_user(db_session)

    db_session.add(NotificationPreference(user_id=user.id))
    db_session.flush()

    db_session.add(NotificationPreference(user_id=user.id))
    with pytest.raises(IntegrityError):
        db_session.flush()
