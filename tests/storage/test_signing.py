"""Tests for presigned URL issuance.

Post-expiry rejection is not reliably reproducible under the in-process mock,
so it is not asserted here.
"""

from __future__ import annotations

import pytest
import requests

from app.storage.references import ReferenceError
from app.storage.signing import generate_signed_url
from tests.storage.conftest import S3Harness


def test_signed_url_fetches_object(s3: S3Harness) -> None:
    key = "snapshots/calf.jpg"
    s3.client.put_object(Bucket=s3.bucket, Key=key, Body=b"snapshot-bytes")

    signed = generate_signed_url(f"s3://{s3.bucket}/{key}", settings=s3.settings, client=s3.client)
    resp = requests.get(signed.url, timeout=10)
    assert resp.status_code == 200
    assert resp.content == b"snapshot-bytes"


def test_ttl_defaults_to_settings(s3: S3Harness) -> None:
    signed = generate_signed_url(
        "s3://moo-snapshots/snapshots/calf.jpg",
        settings=s3.settings,
        client=s3.client,
    )
    assert signed.ttl_seconds == s3.settings.signed_url_ttl_seconds


def test_ttl_is_configurable(s3: S3Harness) -> None:
    signed = generate_signed_url(
        "s3://moo-snapshots/snapshots/calf.jpg",
        ttl=5,
        settings=s3.settings,
        client=s3.client,
    )
    assert signed.ttl_seconds == 5
    # The requested expiry is reflected in the signed request params.
    assert "Expires=" in signed.url or "X-Amz-Expires=5" in signed.url


def test_foreign_reference_is_never_signed(s3: S3Harness) -> None:
    with pytest.raises(ReferenceError):
        generate_signed_url(
            "s3://evil-bucket/snapshots/calf.jpg",
            settings=s3.settings,
            client=s3.client,
        )
