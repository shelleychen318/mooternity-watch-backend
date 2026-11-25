# Snapshot upload contract (edge device → backend → S3)

How an edge device uploads a snapshot image. The device never receives AWS
credentials and never chooses where the object lands: it asks the backend for a
short-lived, pre-authorized upload URL, uploads the bytes directly to S3, then
references the returned key in the event it later posts.

## Flow

```
device ──(1) POST /v1/snapshots/upload-url (Bearer device key)──> backend
device <──(2) { upload_url, key, ttl_seconds } ────────────────── backend
device ──(3) PUT <upload_url>  (raw image bytes, no AWS creds) ──> S3
device ──(4) later: event payload with snapshot.url = <key> ─────> backend
```

## Authentication

Every request to the backend carries the device credential as a bearer token:

```
Authorization: Bearer <device_key>
```

- The `device_key` is provisioned out-of-band (an operator seeds it; see
  `scripts/seed_device.py`) and configured onto the device.
- Send it only over HTTPS. Never place it in a URL or query string.
- A missing, malformed, or unknown credential returns **401**.

## 1–2. Request an upload URL

`POST /v1/snapshots/upload-url`

Request body:

```json
{ "event_id": "evt_2026_01_31_0007" }
```

- `event_id` — the id the device will also put on the event it posts for this
  snapshot, so the image and the event line up. Allowed characters: letters,
  digits, `.`, `_`, `-`; 1–128 chars. Anything else returns **422**.

Response (`200`):

```json
{
  "upload_url": "https://moo-snapshots.s3.us-east-2.amazonaws.com/snapshots/<farm_id>/evt_2026_01_31_0007.jpg?X-Amz-...",
  "key": "snapshots/<farm_id>/evt_2026_01_31_0007.jpg",
  "ttl_seconds": 300
}
```

- `upload_url` — presigned `PUT` URL. Valid for `ttl_seconds` (default **300s**).
- `key` — the canonical object key. The device does **not** choose this; the
  backend derives it from the authenticated device's farm. Use it verbatim as
  the snapshot reference in the event payload.
- The device cannot write outside its own farm's prefix — the farm segment is
  taken from the authenticated device, not from the request.

## 3. Upload the bytes

Plain HTTP `PUT` of the raw image bytes to `upload_url`. No AWS credentials, no
special headers required:

```
PUT <upload_url>
<binary image bytes>
```

A `200` means the object is stored. After `ttl_seconds` the URL is rejected
(`403`) — request a fresh one if the upload is retried past the TTL.

## 4. Reference it in the event

In the event payload, set the snapshot reference to the returned `key`:

```json
{
  "event_id": "evt_2026_01_31_0007",
  "snapshot": { "url": "snapshots/<farm_id>/evt_2026_01_31_0007.jpg", "...": "..." }
}
```

(The event-ingest endpoint itself is delivered separately; this contract covers
only obtaining the upload URL and uploading the bytes.)

## Reference values

| Item | Value |
|---|---|
| Bucket | `moo-snapshots` (private; reachable only via signed URLs) |
| Region | `us-east-2` |
| Key layout | `snapshots/{farm_id}/{event_id}.jpg` |
| URL TTL | 300s (default) |
| Upload method | HTTP `PUT` of raw bytes |
| Canonical reference | the `key` returned by the upload-URL endpoint |
