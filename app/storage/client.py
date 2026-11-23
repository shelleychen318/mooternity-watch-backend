"""boto3 S3 client factory.

The client is built from :class:`~app.config.Settings`. When
``s3_endpoint_url`` is set, requests go to that endpoint with path-style
addressing (``http://host:port/bucket/key``), which S3-compatible stores
require; when unset, requests go to AWS S3 with default virtual-host
addressing.
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

import boto3
from botocore.config import Config

from app.config import Settings, get_settings

if TYPE_CHECKING:  # pragma: no cover - typing only
    from mypy_boto3_s3 import S3Client
else:
    S3Client = object


def build_s3_client(settings: Settings) -> S3Client:
    """Build an uncached boto3 S3 client from ``settings``.

    Prefer :func:`get_s3_client`; this builder lets callers construct a client
    against overridden ``Settings`` without clearing the cache.
    """
    client_kwargs: dict[str, object] = {"region_name": settings.s3_region}

    # When creds are unset, botocore's default provider chain supplies them.
    if settings.s3_access_key_id and settings.s3_secret_access_key:
        client_kwargs["aws_access_key_id"] = settings.s3_access_key_id
        client_kwargs["aws_secret_access_key"] = settings.s3_secret_access_key

    if settings.s3_endpoint_url:
        # S3-compatible store (local mock): path-style addressing.
        client_kwargs["endpoint_url"] = settings.s3_endpoint_url
        client_kwargs["config"] = Config(s3={"addressing_style": "path"})
    else:
        # Real AWS S3: pin the regional endpoint so presigned URLs sign and
        # address the same host. Otherwise botocore may sign the regional host
        # but build a global-host (s3.amazonaws.com) URL, yielding
        # SignatureDoesNotMatch / 403 on fetch for buckets outside us-east-1.
        client_kwargs["endpoint_url"] = f"https://s3.{settings.s3_region}.amazonaws.com"

    return boto3.client("s3", **client_kwargs)


@lru_cache
def get_s3_client() -> S3Client:
    """Return a cached S3 client built from the active settings."""
    return build_s3_client(get_settings())
