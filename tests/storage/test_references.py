"""Tests for snapshot reference validation and resolution."""

from __future__ import annotations

import pytest

from app.storage.references import (
    ReferenceError,
    SnapshotNotFoundError,
    parse_reference,
    resolve_reference,
    validate_reference,
)
from tests.storage.conftest import S3Harness

# --- parsing ----------------------------------------------------------------


def test_parse_s3_uri(s3: S3Harness) -> None:
    ref = parse_reference("s3://moo-snapshots/snapshots/calf.jpg", settings=s3.settings)
    assert ref.bucket == "moo-snapshots"
    assert ref.key == "snapshots/calf.jpg"


def test_parse_virtual_host_url(s3: S3Harness) -> None:
    ref = parse_reference(
        "https://moo-snapshots.s3.us-east-1.amazonaws.com/snapshots/calf.jpg",
        settings=s3.settings,
    )
    assert ref.bucket == "moo-snapshots"
    assert ref.key == "snapshots/calf.jpg"


def test_parse_path_style_url(s3: S3Harness) -> None:
    ref = parse_reference(
        "http://localhost:9000/moo-snapshots/snapshots/calf.jpg",
        settings=s3.settings,
    )
    assert ref.bucket == "moo-snapshots"
    assert ref.key == "snapshots/calf.jpg"


def test_parse_bare_key_uses_configured_bucket(s3: S3Harness) -> None:
    ref = parse_reference("snapshots/calf.jpg", settings=s3.settings)
    assert ref.bucket == "moo-snapshots"
    assert ref.key == "snapshots/calf.jpg"


def test_parse_empty_reference_rejected(s3: S3Harness) -> None:
    with pytest.raises(ReferenceError):
        parse_reference("   ", settings=s3.settings)


# --- validation (trust boundary) --------------------------------------------


def test_validate_accepts_configured_bucket_and_prefix(s3: S3Harness) -> None:
    ref = validate_reference("s3://moo-snapshots/snapshots/calf.jpg", settings=s3.settings)
    assert ref.bucket == "moo-snapshots"


def test_validate_rejects_foreign_bucket(s3: S3Harness) -> None:
    with pytest.raises(ReferenceError, match="not the configured"):
        validate_reference("s3://evil-bucket/snapshots/calf.jpg", settings=s3.settings)


def test_validate_rejects_out_of_prefix_key(s3: S3Harness) -> None:
    with pytest.raises(ReferenceError, match="outside the allowed snapshot prefix"):
        validate_reference("s3://moo-snapshots/secrets/calf.jpg", settings=s3.settings)


# --- resolution against the store -------------------------------------------


def test_resolve_existing_object(s3: S3Harness) -> None:
    key = "snapshots/calf.jpg"
    s3.client.put_object(
        Bucket=s3.bucket, Key=key, Body=b"snapshot-bytes", ContentType="image/jpeg"
    )

    resolved = resolve_reference(f"s3://{s3.bucket}/{key}", settings=s3.settings, client=s3.client)
    assert resolved.reference.key == key
    assert resolved.size == len(b"snapshot-bytes")
    assert resolved.content_type == "image/jpeg"


def test_resolve_missing_key_reports_not_found(s3: S3Harness) -> None:
    with pytest.raises(SnapshotNotFoundError):
        resolve_reference(
            "s3://moo-snapshots/snapshots/missing.jpg",
            settings=s3.settings,
            client=s3.client,
        )


def test_resolve_foreign_bucket_rejected_before_store(s3: S3Harness) -> None:
    # Rejected at validation, never reaching head_object.
    with pytest.raises(ReferenceError):
        resolve_reference(
            "s3://evil-bucket/snapshots/calf.jpg",
            settings=s3.settings,
            client=s3.client,
        )
