"""Centralized, environment-driven configuration (M0-T3).

Settings load from environment variables (and an optional ``.env`` file for local
dev). Values have sane local defaults where it is safe to do so; genuine secrets
have no default and fail fast with a clear error when missing in non-local
environments.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache

from pydantic import Field, PostgresDsn, ValidationError, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    LOCAL = "local"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """Application settings.

    Attributes map to the design doc's config needs: DB URL, S3 creds/bucket,
    Twilio, FCM, signed-URL TTL, retention window, and the auth secret.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="MW_",
        extra="ignore",
    )

    environment: Environment = Environment.LOCAL

    # --- Database -----------------------------------------------------------
    # Default points at the docker-compose Postgres service for local dev.
    database_url: PostgresDsn = Field(
        default="postgresql+psycopg://moo:moo@localhost:5432/mooternity",
    )

    # --- Object storage (S3 / MinIO) ---------------------------------------
    s3_endpoint_url: str | None = Field(
        default="http://localhost:9000",
        description="Override for S3-compatible stores (local dev); None for real AWS S3.",
    )
    s3_region: str = "us-east-1"
    s3_bucket: str = "moo-snapshots"
    s3_access_key_id: str | None = Field(default="minioadmin")
    s3_secret_access_key: str | None = Field(default="minioadmin")
    signed_url_ttl_seconds: int = Field(default=300, ge=1)

    # --- Retention ----------------------------------------------------------
    # Open question in the design doc; default of 90 days is a placeholder.
    retention_days: int = Field(default=90, ge=1)

    # --- Notifications: Twilio (SMS) ---------------------------------------
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_from_number: str | None = None

    # --- Notifications: Firebase Cloud Messaging (push) --------------------
    fcm_credentials_json: str | None = None

    # --- Auth ---------------------------------------------------------------
    auth_secret: str = Field(
        default="dev-insecure-change-me",
        description="Secret for signing user session tokens.",
    )
    auth_token_ttl_seconds: int = Field(default=3600, ge=1)

    @property
    def is_local(self) -> bool:
        return self.environment in (Environment.LOCAL, Environment.TEST)

    @model_validator(mode="after")
    def _require_secrets_outside_local(self) -> Settings:
        """Fail fast when required secrets are missing in staging/production."""
        if self.is_local:
            return self

        missing: list[str] = []
        if self.auth_secret == "dev-insecure-change-me":
            missing.append("MW_AUTH_SECRET (must be set to a real secret)")
        if not self.s3_access_key_id:
            missing.append("MW_S3_ACCESS_KEY_ID")
        if not self.s3_secret_access_key:
            missing.append("MW_S3_SECRET_ACCESS_KEY")

        if missing:
            raise ValueError(
                "Missing required configuration for environment "
                f"'{self.environment.value}': " + ", ".join(missing)
            )
        return self


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance.

    Raises a clear error if configuration is invalid so startup fails fast.
    """
    try:
        return Settings()
    except ValidationError as exc:  # pragma: no cover - exercised via tests
        raise RuntimeError(f"Invalid configuration:\n{exc}") from exc
