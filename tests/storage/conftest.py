"""Fixtures backing storage tests with an in-memory S3 via ``moto``.

``moto`` patches botocore, so a client built from a ``Settings`` with
``s3_endpoint_url`` unset is served by the in-memory mock without a container
or AWS credentials.
"""

from __future__ import annotations

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
