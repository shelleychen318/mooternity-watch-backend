"""Tests for the retention purge job.

These require Postgres and skip when none is reachable, as the model tests do.
"""

from __future__ import annotations

import datetime

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Event
from app.storage.retention import PurgeError, purge
from tests.conftest import make_device, make_event
from tests.storage.conftest import S3Harness

NOW = datetime.datetime.now(datetime.UTC)
CUTOFF = NOW - datetime.timedelta(days=90)


def _seed_event(
    session: Session,
    s3: S3Harness,
    *,
    event_id: str,
    key: str,
    event_timestamp: datetime.datetime,
) -> Event:
    """Create an event with a snapshot reference + upload the object."""
    device = make_device(session, device_key=f"dev_{event_id}")
    event = make_event(session, device=device, event_id=event_id)
    event.snapshot = {"url": f"s3://{s3.bucket}/{key}"}
    event.event_timestamp = event_timestamp
    session.flush()
    s3.put(key)
    return event


def _object_exists(s3: S3Harness, key: str) -> bool:
    listing = s3.client.list_objects_v2(Bucket=s3.bucket, Prefix=key)
    return any(obj["Key"] == key for obj in listing.get("Contents", []))


def test_purge_deletes_only_old_events(db_session: Session, s3: S3Harness) -> None:
    old_key = "snapshots/old.jpg"
    new_key = "snapshots/new.jpg"
    _seed_event(
        db_session,
        s3,
        event_id="evt_old",
        key=old_key,
        event_timestamp=NOW - datetime.timedelta(days=120),
    )
    _seed_event(
        db_session,
        s3,
        event_id="evt_new",
        key=new_key,
        event_timestamp=NOW - datetime.timedelta(days=1),
    )

    summary = purge(CUTOFF, session=db_session, settings=s3.settings, client=s3.client)

    assert summary.dry_run is False
    assert summary.event_count == 1
    assert summary.deleted_keys == [old_key]

    # Old row + object gone; recent row + object retained.
    remaining = db_session.execute(select(Event.event_id)).scalars().all()
    assert remaining == ["evt_new"]
    assert not _object_exists(s3, old_key)
    assert _object_exists(s3, new_key)


def test_dry_run_changes_nothing(db_session: Session, s3: S3Harness) -> None:
    old_key = "snapshots/old.jpg"
    _seed_event(
        db_session,
        s3,
        event_id="evt_old",
        key=old_key,
        event_timestamp=NOW - datetime.timedelta(days=120),
    )

    summary = purge(
        CUTOFF, dry_run=True, session=db_session, settings=s3.settings, client=s3.client
    )

    assert summary.dry_run is True
    assert summary.event_count == 1
    assert summary.deleted_keys == [old_key]

    # Nothing actually removed.
    remaining = db_session.execute(select(Event.event_id)).scalars().all()
    assert remaining == ["evt_old"]
    assert _object_exists(s3, old_key)


def test_cutoff_defaults_to_retention_days(db_session: Session, s3: S3Harness) -> None:
    # settings.retention_days defaults to 90; an event 120 days old is stale.
    _seed_event(
        db_session,
        s3,
        event_id="evt_old",
        key="snapshots/old.jpg",
        event_timestamp=NOW - datetime.timedelta(days=120),
    )

    summary = purge(session=db_session, settings=s3.settings, client=s3.client)
    assert summary.event_count == 1


class _DeleteErrorClient:
    """Wraps an S3 client so delete_objects reports a per-key failure.

    S3 returns HTTP 200 with an ``Errors`` list on partial failure rather than
    raising; this reproduces that so we can assert purge aborts before rows.
    """

    def __init__(self, inner: object) -> None:
        self._inner = inner

    def __getattr__(self, name: str) -> object:
        return getattr(self._inner, name)

    def delete_objects(self, **kwargs: object) -> dict:
        objects = kwargs["Delete"]["Objects"]
        return {
            "Errors": [
                {"Key": o["Key"], "Code": "AccessDenied", "Message": "nope"} for o in objects
            ]
        }


def test_purge_raises_and_keeps_rows_when_delete_fails(db_session: Session, s3: S3Harness) -> None:
    old_key = "snapshots/old.jpg"
    _seed_event(
        db_session,
        s3,
        event_id="evt_old",
        key=old_key,
        event_timestamp=NOW - datetime.timedelta(days=120),
    )

    failing_client = _DeleteErrorClient(s3.client)
    with pytest.raises(PurgeError):
        purge(CUTOFF, session=db_session, settings=s3.settings, client=failing_client)

    # The row must survive: a failed object delete must not delete the row, or the
    # object would be stranded with no reference pointing at it.
    remaining = db_session.execute(select(Event.event_id)).scalars().all()
    assert remaining == ["evt_old"]
    assert _object_exists(s3, old_key)
