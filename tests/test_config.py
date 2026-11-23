"""Tests for configuration loading and fail-fast validation."""

import pytest
from pydantic import ValidationError

from app.config import Environment, Settings


def test_local_defaults_load():
    s = Settings(environment=Environment.LOCAL)
    assert s.is_local
    assert s.signed_url_ttl_seconds == 300
    assert str(s.database_url).startswith("postgresql")


def test_production_requires_auth_secret():
    with pytest.raises(ValidationError) as exc:
        Settings(
            environment=Environment.PRODUCTION,
            s3_access_key_id="key",
            s3_secret_access_key="secret",
        )
    assert "MW_AUTH_SECRET" in str(exc.value)


def test_production_with_all_secrets_ok():
    s = Settings(
        environment=Environment.PRODUCTION,
        auth_secret="a-real-secret",
        s3_access_key_id="key",
        s3_secret_access_key="secret",
    )
    assert not s.is_local
    assert s.auth_secret == "a-real-secret"


def test_production_real_aws_needs_no_s3_keys():
    """Against real AWS S3 (no endpoint override), the Fargate task role supplies
    credentials, so startup must succeed with S3 keys unset."""
    s = Settings(
        environment=Environment.PRODUCTION,
        auth_secret="a-real-secret",
        s3_endpoint_url=None,
        s3_access_key_id=None,
        s3_secret_access_key=None,
    )
    assert s.s3_access_key_id is None
    assert s.s3_endpoint_url is None


def test_production_custom_endpoint_still_requires_s3_keys():
    """A custom S3-compatible endpoint needs explicit credentials, so missing keys
    outside local must still fail fast."""
    with pytest.raises(ValidationError) as exc:
        Settings(
            environment=Environment.PRODUCTION,
            auth_secret="a-real-secret",
            s3_endpoint_url="http://minio:9000",
            s3_access_key_id=None,
            s3_secret_access_key=None,
        )
    assert "MW_S3_ACCESS_KEY_ID" in str(exc.value)
