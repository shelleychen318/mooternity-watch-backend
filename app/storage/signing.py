"""Short-lived presigned URLs for reading snapshot objects.

A presigned ``GET`` URL expires after a configurable TTL. The reference is
validated against the configured bucket and prefix before signing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.config import Settings, get_settings
from app.storage.client import get_s3_client
from app.storage.references import validate_reference

if TYPE_CHECKING:  # pragma: no cover - typing only
    from mypy_boto3_s3 import S3Client
else:
    S3Client = object


@dataclass(frozen=True)
class SignedUrl:
    """A presigned URL and the TTL (seconds) it was signed with."""

    url: str
    ttl_seconds: int


def generate_signed_url(
    ref: str,
    *,
    ttl: int | None = None,
    settings: Settings | None = None,
    client: S3Client | None = None,
) -> SignedUrl:
    """Issue a short-lived presigned GET URL for a snapshot reference.

    The reference is validated against the configured bucket + snapshot prefix
    before signing; a foreign-bucket or out-of-prefix reference raises
    ``ReferenceError`` and is never signed.

    Args:
        ref: the stored snapshot reference (s3 URI, S3 URL, or bare key).
        ttl: URL lifetime in seconds. Defaults to
            ``settings.signed_url_ttl_seconds`` (300s by default).

    Returns:
        The presigned URL together with its effective TTL.
    """
    settings = settings or get_settings()
    reference = validate_reference(ref, settings=settings)
    client = client or get_s3_client()

    effective_ttl = ttl if ttl is not None else settings.signed_url_ttl_seconds

    url = client.generate_presigned_url(
        "get_object",
        Params={"Bucket": reference.bucket, "Key": reference.key},
        ExpiresIn=effective_ttl,
    )
    return SignedUrl(url=url, ttl_seconds=effective_ttl)
