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


def test_s3_has_no_code_defaults(monkeypatch):
    """S3 endpoint and keys have no code defaults; unset, they load as None (real-AWS
    task-role path). The MinIO values live only in .env, so they cannot leak into a
    deploy. _env_file=None + delenv mimic the Fargate task (no .env, vars unset)."""
    for var in ("MW_S3_ENDPOINT_URL", "MW_S3_ACCESS_KEY_ID", "MW_S3_SECRET_ACCESS_KEY"):
        monkeypatch.delenv(var, raising=False)
    s = Settings(
        environment=Environment.STAGING,
        auth_secret="a-real-secret",
        _env_file=None,
    )
    assert s.s3_endpoint_url is None
    assert s.s3_access_key_id is None
    assert s.s3_secret_access_key is None
