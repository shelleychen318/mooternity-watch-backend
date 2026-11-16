"""Tests for the S3 client factory."""

from __future__ import annotations

from app.config import Environment, Settings
from app.storage.client import build_s3_client
from tests.storage.conftest import S3Harness


def test_client_reaches_store(s3: S3Harness) -> None:
    s3.client.head_bucket(Bucket=s3.bucket)

    listing = s3.client.list_objects_v2(Bucket=s3.bucket)
    assert listing.get("KeyCount", 0) == 0

    s3.put(f"{s3.prefix}calf.jpg")
    listing = s3.client.list_objects_v2(Bucket=s3.bucket)
    keys = [obj["Key"] for obj in listing.get("Contents", [])]
    assert keys == [f"{s3.prefix}calf.jpg"]


def test_path_style_applied_only_with_endpoint_override() -> None:
    mock_settings = Settings(
        environment=Environment.TEST,
        s3_endpoint_url="http://localhost:9000",
    )
    client = build_s3_client(mock_settings)
    assert client.meta.config.s3["addressing_style"] == "path"

    real_settings = Settings(
        environment=Environment.TEST,
        s3_endpoint_url=None,
    )
    client = build_s3_client(real_settings)
    s3_config = client.meta.config.s3 or {}
    assert s3_config.get("addressing_style") != "path"
