"""Snapshot upload-URL endpoint. Auth decisions live in ``test_device_auth``."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
import requests
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import Environment, Settings
from app.storage.client import build_s3_client
from tests.conftest import make_device
from tests.storage.conftest import S3Harness

UPLOAD_URL_PATH = "/v1/snapshots/upload-url"
VALID_KEY = "dev_seeded_key_for_tests"


@pytest.fixture
def wired_s3(monkeypatch: pytest.MonkeyPatch) -> Iterator[S3Harness]:
    """In-process S3 (moto) with the endpoint's settings + client pointed at it."""
    moto = pytest.importorskip("moto")
    settings = Settings(
        environment=Environment.TEST,
        s3_endpoint_url=None,
        s3_region="us-east-1",
        s3_bucket="moo-snapshots",
        s3_snapshot_prefix="snapshots/",
        s3_access_key_id="testing",
        s3_secret_access_key="testing",
    )
    with moto.mock_aws():
        client = build_s3_client(settings)
        client.create_bucket(Bucket=settings.s3_bucket)
        monkeypatch.setattr("app.api.snapshots.get_settings", lambda: settings)
        monkeypatch.setattr(
            "app.storage.signing.get_s3_client",
            lambda: build_s3_client(settings),
        )
        yield S3Harness(
            client=client,
            settings=settings,
            bucket=settings.s3_bucket,
            prefix=settings.s3_snapshot_prefix,
        )


def _post(client: TestClient, event_id: str) -> object:
    return client.post(
        UPLOAD_URL_PATH,
        json={"event_id": event_id},
        headers={"Authorization": f"Bearer {VALID_KEY}"},
    )


def test_key_is_scoped_to_device_farm(
    client: TestClient, db_session: Session, wired_s3: S3Harness
) -> None:
    device = make_device(db_session, device_key=VALID_KEY)

    resp = _post(client, "evt_123")
    assert resp.status_code == 200

    body = resp.json()
    assert body["key"] == f"snapshots/{device.farm_id}/evt_123.jpg"
    assert body["key"].startswith(wired_s3.prefix)
    assert body["ttl_seconds"] == wired_s3.settings.signed_url_ttl_seconds
    assert body["upload_url"]


def test_minted_url_accepts_an_upload(
    client: TestClient, db_session: Session, wired_s3: S3Harness
) -> None:
    make_device(db_session, device_key=VALID_KEY)

    body = _post(client, "evt_upload").json()
    put = requests.put(body["upload_url"], data=b"snapshot-bytes", timeout=10)
    assert put.status_code == 200

    stored = wired_s3.client.get_object(Bucket=wired_s3.bucket, Key=body["key"])
    assert stored["Body"].read() == b"snapshot-bytes"


def test_device_cannot_escape_its_farm_prefix(
    client: TestClient, db_session: Session, wired_s3: S3Harness
) -> None:
    device = make_device(db_session, device_key=VALID_KEY)

    # A path-traversal event_id is rejected, so the key stays under the farm.
    assert _post(client, "../other-farm/evt").status_code == 422

    ok = _post(client, "evt_ok")
    assert ok.status_code == 200
    assert ok.json()["key"].startswith(f"snapshots/{device.farm_id}/")
