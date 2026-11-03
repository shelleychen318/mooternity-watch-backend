"""Tests for configuration loading and fail-fast validation (M0-T3)."""

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
