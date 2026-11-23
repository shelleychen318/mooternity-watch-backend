"""Snapshot reference parsing, validation, and resolution.

Snapshot images are uploaded to S3 by the edge device; the backend stores only
references to them. A reference arrives untrusted and must be validated before
use: it must target the configured bucket and a key under the allowed prefix.

Accepted reference forms, each resolved to a ``(bucket, key)`` pair:

- ``s3://bucket/key``
- virtual-host-style URL: ``https://bucket.s3.region.amazonaws.com/key``
- path-style URL: ``http://host:port/bucket/key``
- a bare key (``snapshots/....jpg``), taken to live in the configured bucket
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib.parse import unquote, urlparse

from botocore.exceptions import ClientError

from app.config import Settings, get_settings
from app.storage.client import get_s3_client

if TYPE_CHECKING:  # pragma: no cover - typing only
    from mypy_boto3_s3 import S3Client
else:
    S3Client = object


class ReferenceError(ValueError):
    """A snapshot reference is malformed or outside the trust boundary."""


class SnapshotNotFoundError(LookupError):
    """A valid reference points at an object that does not exist."""


@dataclass(frozen=True)
class SnapshotReference:
    """A parsed, validated reference to a snapshot object."""

    bucket: str
    key: str


@dataclass(frozen=True)
class ResolvedSnapshot:
    """Result of resolving a reference against the store."""

    reference: SnapshotReference
    size: int
    content_type: str | None


def parse_reference(ref: str, *, settings: Settings | None = None) -> SnapshotReference:
    """Parse a raw reference string into a ``(bucket, key)`` pair.

    This only parses — it does not check the bucket/prefix allow-list (see
    :func:`validate_reference`) or whether the object exists. A bare key is
    interpreted as living in the configured bucket.

    Raises:
        ReferenceError: the reference is empty or cannot be parsed into a key.
    """
    settings = settings or get_settings()

    if not ref or not ref.strip():
        raise ReferenceError("Empty snapshot reference.")

    ref = ref.strip()
    parsed = urlparse(ref)
    scheme = parsed.scheme.lower()

    if scheme == "s3":
        # s3://bucket/key
        bucket = parsed.netloc
        key = parsed.path.lstrip("/")
    elif scheme in ("http", "https"):
        bucket, key = _parse_http_reference(parsed, settings)
    elif not scheme:
        # Bare key -> configured bucket.
        bucket = settings.s3_bucket
        key = ref.lstrip("/")
    else:
        raise ReferenceError(f"Unsupported reference scheme: {scheme!r}")

    key = unquote(key)
    if not key:
        raise ReferenceError(f"Reference has no object key: {ref!r}")

    return SnapshotReference(bucket=bucket, key=key)


def _parse_http_reference(parsed, settings: Settings) -> tuple[str, str]:
    """Extract ``(bucket, key)`` from an http(s) S3 URL.

    Handles both virtual-host-style (``bucket.s3....amazonaws.com/key``) and
    path-style (``host/bucket/key``) URLs. For virtual-host style we only treat
    the leading label as a bucket when the host is an AWS S3 endpoint; any other
    host is treated as path-style.
    """
    host = parsed.netloc.split(":")[0].lower()
    path = parsed.path.lstrip("/")

    # Virtual-host style: <bucket>.s3[.-]<region>.amazonaws.com or
    # <bucket>.s3.amazonaws.com. The bucket is the label(s) before ".s3".
    if ".amazonaws.com" in host and ".s3" in host:
        bucket = host.split(".s3", 1)[0]
        if bucket:
            return bucket, path

    # Path-style: first path segment is the bucket, the rest is the key.
    first, _, rest = path.partition("/")
    if not rest:
        # Only a bucket with no key, or a single path segment we must treat as
        # a bucket-less key under the configured bucket.
        return settings.s3_bucket, path
    return first, rest


def validate_reference(ref: str, *, settings: Settings | None = None) -> SnapshotReference:
    """Parse ``ref`` and enforce the bucket + prefix trust boundary.

    Raises:
        ReferenceError: the reference targets a bucket other than the configured
            one, or a key outside the configured snapshot prefix.
    """
    settings = settings or get_settings()
    reference = parse_reference(ref, settings=settings)

    if reference.bucket != settings.s3_bucket:
        raise ReferenceError(
            f"Reference bucket {reference.bucket!r} is not the configured "
            f"snapshot bucket {settings.s3_bucket!r}."
        )

    prefix = settings.s3_snapshot_prefix
    if prefix and not reference.key.startswith(prefix):
        raise ReferenceError(
            f"Reference key {reference.key!r} is outside the allowed snapshot prefix {prefix!r}."
        )

    return reference


def resolve_reference(
    ref: str,
    *,
    settings: Settings | None = None,
    client: S3Client | None = None,
) -> ResolvedSnapshot:
    """Validate ``ref`` and confirm the object exists via ``head_object``.

    Returns the object's size and content-type on success.

    Raises:
        ReferenceError: the reference is malformed or outside the trust boundary.
        SnapshotNotFoundError: the reference is valid but the object is missing.
    """
    settings = settings or get_settings()
    reference = validate_reference(ref, settings=settings)
    client = client or get_s3_client()

    try:
        head = client.head_object(Bucket=reference.bucket, Key=reference.key)
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code")
        if error_code in ("404", "NoSuchKey", "NotFound"):
            raise SnapshotNotFoundError(
                f"Snapshot object not found: s3://{reference.bucket}/{reference.key}"
            ) from exc
        raise

    return ResolvedSnapshot(
        reference=reference,
        size=head.get("ContentLength", 0),
        content_type=head.get("ContentType"),
    )
