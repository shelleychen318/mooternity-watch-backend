from __future__ import annotations

import datetime

from sqlalchemy import Engine, inspect
from sqlalchemy.orm import Session

from app.models import Notification, NotificationChannel, NotificationStatus
from tests.conftest import make_alert, make_user


def test_notification_pending_to_sent(db_session: Session):
    alert = make_alert(db_session)
    user = make_user(db_session)

    notif = Notification(
        alert_id=alert.id,
        user_id=user.id,
        channel=NotificationChannel.SMS,
    )
    db_session.add(notif)
    db_session.flush()
    assert notif.status == NotificationStatus.PENDING
    assert notif.attempts == 0

    notif.status = NotificationStatus.SENT
    notif.sent_at = datetime.datetime.now(datetime.UTC)
    db_session.flush()
    db_session.expire(notif)
    fetched = db_session.get(Notification, notif.id)
    assert fetched.status == NotificationStatus.SENT
    assert fetched.sent_at is not None


def test_notification_pending_to_failed(db_session: Session):
    alert = make_alert(db_session)
    user = make_user(db_session)

    notif = Notification(
        alert_id=alert.id,
        user_id=user.id,
        channel=NotificationChannel.PUSH,
    )
    db_session.add(notif)
    db_session.flush()

    notif.status = NotificationStatus.FAILED
    notif.attempts = 3
    notif.last_error = "provider timeout"
    notif.next_retry_at = datetime.datetime.now(datetime.UTC)
    db_session.flush()
    db_session.expire(notif)
    fetched = db_session.get(Notification, notif.id)
    assert fetched.status == NotificationStatus.FAILED
    assert fetched.attempts == 3
    assert fetched.last_error == "provider timeout"


def test_polling_index_exists(db_session: Session, test_engine: Engine):
    insp = inspect(test_engine)
    indexes = insp.get_indexes("notifications")
    match = [ix for ix in indexes if ix["column_names"] == ["status", "next_retry_at"]]
    assert match, (
        "Expected a composite index on (status, next_retry_at); "
        f"found: {[ix['column_names'] for ix in indexes]}"
    )
