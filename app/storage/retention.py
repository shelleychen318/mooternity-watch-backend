"""Retention purge for events and their snapshot objects.

Events outside the retention window (``settings.retention_days`` by default)
and the snapshot objects they reference are deleted. Objects are deleted before
rows so a failure cannot leave a row referencing a deleted object; deletes are
batched since S3 ``delete_objects`` accepts at most 1000 keys per call. With
``dry_run=True`` the plan is logged and nothing is deleted.

An event's age is taken from ``event_timestamp`` (device capture time), falling
back to ``received_timestamp`` (server ingestion time).
"""

from __future__ import annotations

import datetime
import logging
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, TypeVar

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models import Event
from app.storage.client import get_s3_client
from app.storage.references import ReferenceError, parse_reference

if TYPE_CHECKING:  # pragma: no cover - typing only
    from mypy_boto3_s3 import S3Client
else:
    S3Client = object

logger = logging.getLogger(__name__)


class PurgeError(RuntimeError):
    """An object deletion failed, so the purge was aborted before deleting rows.

    S3 ``delete_objects`` returns HTTP 200 even when individual keys fail, listing
    them under ``Errors``. We raise on any such failure so DB rows are never
    deleted while their snapshot objects remain — which would strand the objects
    (no row left to find them by).
    """


# S3 delete_objects accepts at most 1000 keys per request.
_DELETE_BATCH_SIZE = 1000

_T = TypeVar("_T")


def _batched(items: list[_T], size: int) -> Iterator[list[_T]]:
    """Yield ``items`` in chunks of at most ``size``."""
    for start in range(0, len(items), size):
        yield items[start : start + size]


@dataclass
class PurgeSummary:
    """Outcome of a purge run (or the plan, when ``dry_run``)."""

    dry_run: bool
    cutoff: datetime.datetime
    event_count: int
    deleted_keys: list[str] = field(default_factory=list)
    # Keys referenced by purged events that could not be parsed/validated into
    # a (bucket, key) within the configured bucket; logged, not deleted.
    skipped_keys: list[str] = field(default_factory=list)


def _snapshot_key(event: Event, settings: Settings) -> str | None:
    """Return the snapshot object key for an event, or ``None``.

    Returns ``None`` when the event has no snapshot reference, the reference is
    unparseable, or it targets a bucket other than the configured one.
    """
    snapshot = event.snapshot or {}
    url = snapshot.get("url")
    if not url:
        return None
    try:
        reference = parse_reference(url, settings=settings)
    except ReferenceError:
        return None
    if reference.bucket != settings.s3_bucket:
        return None
    return reference.key


def purge(
    older_than: datetime.datetime | None = None,
    *,
    dry_run: bool = False,
    session: Session,
    settings: Settings | None = None,
    client: S3Client | None = None,
) -> PurgeSummary:
    """Purge events older than the cutoff and their snapshot objects.

    Args:
        older_than: cutoff instant; events at or before it are purged. Defaults
            to ``now - settings.retention_days``.
        dry_run: when True, log the plan and delete nothing.
        session: an open DB session (events live in Postgres).
        settings: configuration (defaults to the cached settings).
        client: S3 client (defaults to the cached client).

    Returns:
        A :class:`PurgeSummary` with the cutoff, the number of events in scope,
        and the snapshot keys deleted (or that would be deleted in a dry run).
    """
    settings = settings or get_settings()
    if older_than is None:
        older_than = datetime.datetime.now(datetime.UTC) - datetime.timedelta(
            days=settings.retention_days
        )

    # Rows with both timestamps null have a null age and are not selected.
    age_column = func.coalesce(Event.event_timestamp, Event.received_timestamp)
    stale = session.execute(select(Event).where(age_column <= older_than)).scalars().all()

    keys: list[str] = []
    skipped: list[str] = []
    for event in stale:
        key = _snapshot_key(event, settings)
        if key is not None:
            keys.append(key)
        elif (event.snapshot or {}).get("url"):
            skipped.append((event.snapshot or {}).get("url"))

    summary = PurgeSummary(
        dry_run=dry_run,
        cutoff=older_than,
        event_count=len(stale),
        deleted_keys=keys,
        skipped_keys=skipped,
    )

    if dry_run:
        logger.info(
            "Retention dry-run: would delete %d event(s) and %d snapshot "
            "object(s) older than %s. keys=%s skipped=%s",
            summary.event_count,
            len(keys),
            older_than.isoformat(),
            keys,
            skipped,
        )
        return summary

    client = client or get_s3_client()

    # Delete objects before rows. delete_objects reports per-key failures in the
    # response rather than raising, so check Errors and abort before any row.
    for chunk in _batched(keys, _DELETE_BATCH_SIZE):
        response = client.delete_objects(
            Bucket=settings.s3_bucket,
            Delete={"Objects": [{"Key": key} for key in chunk]},
        )
        errors = response.get("Errors")
        if errors:
            failed = ", ".join(
                f"{e.get('Key')!r} ({e.get('Code')}: {e.get('Message')})" for e in errors
            )
            raise PurgeError(
                f"Aborting purge: {len(errors)} snapshot object(s) failed to delete "
                f"from bucket {settings.s3_bucket!r}; no event rows were deleted. "
                f"Failures: {failed}"
            )

    # Then delete rows.
    for event in stale:
        session.delete(event)
    session.flush()

    logger.info(
        "Retention purge: deleted %d event(s) and %d snapshot object(s) older than %s.",
        summary.event_count,
        len(keys),
        older_than.isoformat(),
    )
    return summary
