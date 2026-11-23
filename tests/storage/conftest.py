"""Fixtures backing storage tests.

Two tiers:

- The offline tier (``s3``/``s3_settings``) uses an in-memory S3 via ``moto``.
  ``moto`` patches botocore, so a client built from a ``Settings`` with
  ``s3_endpoint_url`` unset is served by the in-memory mock without a container
  or AWS credentials. This runs on every commit.

- The real-AWS tier (``s3_real``) talks to a throwaway bucket on real S3. It is
  opt-in and **skips** unless ``MW_S3_REAL_TEST=1`` is set, so the default suite
  and CI are unaffected (mirrors how ``db_session`` skips without Postgres).
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from app.config import Environment, Settings
from app.storage.client import build_s3_client

if TYPE_CHECKING:  # pragma: no cover - typing only
    from mypy_boto3_s3 import S3Client
else:
    S3Client = object

TEST_BUCKET = "moo-snapshots"
TEST_PREFIX = "snapshots/"

# Throwaway buckets for the real-AWS tier are named with this prefix so they are
# obviously disposable and so the CI IAM role (scoped to ``moo-snapshots-citest-*``)
# can create/delete them but can never touch the real ``moo-snapshots`` bucket.
REAL_TEST_BUCKET_PREFIX = "moo-snapshots-citest-"

# Opt-in toggle. The real tier is skipped entirely unless this is set to "1".
REAL_TEST_ENV_FLAG = "MW_S3_REAL_TEST"


@dataclass
class S3Harness:
    """Client, settings, and bucket/prefix for a storage test."""

    client: S3Client
    settings: Settings
    bucket: str
    prefix: str

    def put(self, key: str, body: bytes = b"snapshot-bytes") -> None:
        self.client.put_object(Bucket=self.bucket, Key=key, Body=body)


@pytest.fixture
def s3_settings() -> Settings:
    """Settings with ``s3_endpoint_url`` unset so moto serves the client.

    The credentials are placeholders that satisfy botocore under the mock.
    """
    return Settings(
        environment=Environment.TEST,
        s3_endpoint_url=None,
        s3_region="us-east-1",
        s3_bucket=TEST_BUCKET,
        s3_snapshot_prefix=TEST_PREFIX,
        s3_access_key_id="testing",
        s3_secret_access_key="testing",
    )


@pytest.fixture
def s3(s3_settings: Settings) -> Iterator[S3Harness]:
    """In-process S3 with the snapshots bucket created, yielded as a harness."""
    moto = pytest.importorskip("moto")
    with moto.mock_aws():
        client = build_s3_client(s3_settings)
        client.create_bucket(Bucket=s3_settings.s3_bucket)
        yield S3Harness(
            client=client,
            settings=s3_settings,
            bucket=s3_settings.s3_bucket,
            prefix=s3_settings.s3_snapshot_prefix,
        )


# --- Real-AWS tier (opt-in, skipped unless MW_S3_REAL_TEST=1) ---------------


@dataclass
class S3RealHarness:
    """Client, settings, and the throwaway bucket/prefix for a real-S3 test.

    Mirrors :class:`S3Harness` so the real-tier tests read the same way as the
    offline ones; the difference is entirely in the fixture that builds it.
    """

    client: S3Client
    settings: Settings
    bucket: str
    prefix: str

    def put(self, key: str, body: bytes = b"snapshot-bytes") -> None:
        self.client.put_object(Bucket=self.bucket, Key=key, Body=body)


def _empty_and_delete_bucket(client: S3Client, bucket: str) -> None:
    """Delete every object (paginated) then the bucket itself.

    Paginates because a test run could leave more than the 1000 objects a single
    ``list_objects_v2`` page returns; ``delete_objects`` also caps at 1000 keys.
    """
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket):
        contents = page.get("Contents", [])
        if not contents:
            continue
        client.delete_objects(
            Bucket=bucket,
            Delete={"Objects": [{"Key": obj["Key"]} for obj in contents]},
        )
    client.delete_bucket(Bucket=bucket)


@pytest.fixture
def s3_real() -> Iterator[S3RealHarness]:
    """Provision a throwaway real-S3 bucket for the duration of one test.

    Skips unless ``MW_S3_REAL_TEST=1``. Credentials are supplied by botocore's
    default provider chain (an OIDC role in CI, or the local AWS profile), so no
    keys are read from settings here. The bucket is created in the configured
    region, locked down with a public-access block, and torn down in a
    ``finally`` that empties it, deletes it, and asserts it is gone.
    """
    if os.environ.get(REAL_TEST_ENV_FLAG) != "1":
        pytest.skip(f"Real-S3 tier skipped; set {REAL_TEST_ENV_FLAG}=1 to run it.")

    # Guard against pointing the "real" tier at a mock endpoint by mistake: if a
    # run sets the toggle but leaves an S3 endpoint override in the environment,
    # fail loudly rather than silently testing the wrong store.
    if os.environ.get("MW_S3_ENDPOINT_URL"):
        raise RuntimeError(
            f"{REAL_TEST_ENV_FLAG}=1 but MW_S3_ENDPOINT_URL is set; the real-S3 "
            "tier must run against AWS S3. Unset MW_S3_ENDPOINT_URL."
        )

    region = os.environ.get("MW_S3_REGION", "us-east-2")
    bucket = f"{REAL_TEST_BUCKET_PREFIX}{uuid.uuid4().hex[:12]}"

    # Real AWS: no endpoint override, and leave creds unset so botocore's
    # provider chain (OIDC role / local profile) supplies them.
    settings = Settings(
        environment=Environment.TEST,
        s3_endpoint_url=None,
        s3_region=region,
        s3_bucket=bucket,
        s3_snapshot_prefix=TEST_PREFIX,
        s3_access_key_id=None,
        s3_secret_access_key=None,
    )
    client = build_s3_client(settings)

    # us-east-1 is the one region that must NOT get a LocationConstraint.
    create_kwargs: dict[str, object] = {"Bucket": bucket}
    if region != "us-east-1":
        create_kwargs["CreateBucketConfiguration"] = {"LocationConstraint": region}
    client.create_bucket(**create_kwargs)

    try:
        # Match the prod bucket's posture: snapshots are only reached via signed
        # URLs, so the bucket itself stays fully private.
        client.put_public_access_block(
            Bucket=bucket,
            PublicAccessBlockConfiguration={
                "BlockPublicAcls": True,
                "IgnorePublicAcls": True,
                "BlockPublicPolicy": True,
                "RestrictPublicBuckets": True,
            },
        )
        yield S3RealHarness(
            client=client,
            settings=settings,
            bucket=bucket,
            prefix=settings.s3_snapshot_prefix,
        )
    finally:
        _empty_and_delete_bucket(client, bucket)
        # Teardown must leave nothing behind: confirm the bucket is really gone.
        with pytest.raises(client.exceptions.ClientError):
            client.head_bucket(Bucket=bucket)
