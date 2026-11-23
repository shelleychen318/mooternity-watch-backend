"""Real-AWS behavior tests (opt-in; skipped unless ``MW_S3_REAL_TEST=1``).

These assert the two behaviors the in-process mock cannot faithfully reproduce,
which are also the riskiest parts of the storage layer:

1. **Presigned-URL TTL expiry.** A presigned GET works before its TTL and is
   rejected (HTTP 403) after it. The offline tier only checks the pre-expiry
   fetch because the mock does not enforce expiry.
2. **Real object deletion.** The delete path ``retention.purge`` uses
   (``delete_objects``) actually removes the object from real S3. Under the CI
   OIDC role this doubles as a check that the role is allowed to delete in the
   bucket; locally it runs under whatever identity your AWS profile provides.

The ``s3_real`` fixture provisions and tears down a throwaway
``moo-snapshots-citest-*`` bucket, so these never touch the real snapshot bucket.
"""

from __future__ import annotations

import time

import pytest
import requests

from app.storage.signing import generate_signed_url
from tests.storage.conftest import S3RealHarness

pytestmark = pytest.mark.s3_real

# TTL for the expiry test. Deliberately a few seconds (not 1-2s) so clock skew
# and request latency cannot make the "before expiry" fetch race the deadline.
_SIGNED_URL_TTL = 5
# Extra margin added after the TTL before asserting rejection, to absorb skew.
_EXPIRY_BUFFER = 3


def test_presigned_url_expires(s3_real: S3RealHarness) -> None:
    """A presigned GET succeeds before its TTL and is 403 after it."""
    key = "snapshots/expiring.jpg"
    s3_real.put(key, b"snapshot-bytes")

    signed = generate_signed_url(
        f"s3://{s3_real.bucket}/{key}",
        ttl=_SIGNED_URL_TTL,
        settings=s3_real.settings,
        client=s3_real.client,
    )
    assert signed.ttl_seconds == _SIGNED_URL_TTL

    before = requests.get(signed.url, timeout=10)
    assert before.status_code == 200
    assert before.content == b"snapshot-bytes"

    # Real S3 rejects the stale signature with 403; the mock does not.
    time.sleep(_SIGNED_URL_TTL + _EXPIRY_BUFFER)
    after = requests.get(signed.url, timeout=10)
    assert after.status_code == 403


def test_delete_takes_effect_on_real_s3(s3_real: S3RealHarness) -> None:
    """The delete path used by the purge job really removes the object.

    Exercises the same ``delete_objects`` call ``retention.purge`` makes, against
    real S3 and the real IAM identity, then confirms the object is gone. (The
    event-row join is covered by the offline retention tests, which need a DB;
    here we isolate the S3 side so this stays DB-free.)
    """
    key = "snapshots/to-delete.jpg"
    s3_real.put(key, b"snapshot-bytes")

    head = s3_real.client.head_object(Bucket=s3_real.bucket, Key=key)
    assert head["ContentLength"] == len(b"snapshot-bytes")

    s3_real.client.delete_objects(
        Bucket=s3_real.bucket,
        Delete={"Objects": [{"Key": key}]},
    )

    # head_object on a deleted key raises a 404-class ClientError.
    with pytest.raises(s3_real.client.exceptions.ClientError) as exc_info:
        s3_real.client.head_object(Bucket=s3_real.bucket, Key=key)
    assert exc_info.value.response["Error"]["Code"] in ("404", "NoSuchKey", "NotFound")

    listing = s3_real.client.list_objects_v2(Bucket=s3_real.bucket, Prefix=key)
    assert listing.get("KeyCount", 0) == 0
