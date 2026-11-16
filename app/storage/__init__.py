"""Object storage for snapshot references, signed URLs, and retention."""

from __future__ import annotations

from app.storage.client import build_s3_client, get_s3_client
from app.storage.references import (
    ReferenceError,
    ResolvedSnapshot,
    SnapshotNotFoundError,
    SnapshotReference,
    parse_reference,
    resolve_reference,
    validate_reference,
)
from app.storage.retention import PurgeSummary, purge
from app.storage.signing import SignedUrl, generate_signed_url

__all__ = [
    "PurgeSummary",
    "ReferenceError",
    "ResolvedSnapshot",
    "SignedUrl",
    "SnapshotNotFoundError",
    "SnapshotReference",
    "build_s3_client",
    "generate_signed_url",
    "get_s3_client",
    "parse_reference",
    "purge",
    "resolve_reference",
    "validate_reference",
]
