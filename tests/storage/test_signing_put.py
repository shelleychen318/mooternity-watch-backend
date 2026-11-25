"""Presigned PUT URL issuance (offline tier). Real round-trip: ``test_s3_real``."""

from __future__ import annotations

import pytest
import requests

from app.storage.references import ReferenceError
from app.storage.signing import generate_presigned_put_url
from tests.storage.conftest import S3Harness


def test_presigned_put_uploads_object(s3: S3Harness) -> None:
    key = "snapshots/farm-1/evt_001.jpg"

    signed = generate_presigned_put_url(key, settings=s3.settings, client=s3.client)
    resp = requests.put(signed.url, data=b"snapshot-bytes", timeout=10)
    assert resp.status_code == 200

    stored = s3.client.get_object(Bucket=s3.bucket, Key=key)
    assert stored["Body"].read() == b"snapshot-bytes"


def test_out_of_boundary_key_is_never_signed(s3: S3Harness) -> None:
    # The signer validates against the bucket + prefix before signing.
    for bad in ("not-snapshots/escape.jpg", "s3://evil-bucket/snapshots/evt.jpg"):
        with pytest.raises(ReferenceError):
            generate_presigned_put_url(bad, settings=s3.settings, client=s3.client)
