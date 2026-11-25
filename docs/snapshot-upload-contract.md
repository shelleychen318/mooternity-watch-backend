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

## Base URL

The backend is reached over HTTPS at the deployed host:

```
https://mo-08942879d73e42cfb4f5fc48690e9775.ecs.us-east-2.on.aws
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
  "upload_url": "https://moo-snapshots-prod.s3.us-east-2.amazonaws.com/snapshots/<farm_id>/evt_2026_01_31_0007.jpg?X-Amz-...",
  "key": "snapshots/<farm_id>/evt_2026_01_31_0007.jpg",
  "ttl_seconds": 300
}
```

- `upload_url` — presigned `PUT` URL. Valid for `ttl_seconds` (default **300s**).
  Request it right before uploading; do not cache or reuse it.
- `key` — the canonical object key. The device does **not** choose this; the
  backend derives it from the authenticated device's farm. Use it verbatim as
  the snapshot reference in the event payload.
- `<farm_id>` is a **UUID** (e.g. `9e50a67d-666c-4391-b56d-4e3b03ba1eed`), fixed
  per device. The device cannot write outside its own farm's prefix — the farm
  segment comes from the authenticated device, not from the request.

## 3. Upload the bytes

Plain HTTP `PUT` of the raw image bytes to `upload_url`. No AWS credentials and
no `Authorization` header — the signature is already in the URL:

```
PUT <upload_url>
<binary image bytes>
```

- **Do not add a `Content-Type` (or other signed) header.** The URL is signed
  without one; sending headers S3 expects to be part of the signature causes
  `403 SignatureDoesNotMatch`. Send only the raw body.
- A `200` means the object is stored.
- After `ttl_seconds` the URL is rejected with `403` — if an upload is retried
  past the TTL, request a fresh URL (step 1) and PUT to that.

## 4. Reference it in the event

In the event payload, set the snapshot reference to the returned `key`:

```json
{
  "event_id": "evt_2026_01_31_0007",
  "snapshot": { "url": "snapshots/<farm_id>/evt_2026_01_31_0007.jpg", "...": "..." }
}
```

For the full event payload the backend expects (all fields, types, and the
`snapshot` object shape), see the [Software Design Doc](https://docs.google.com/document/d/19zgMcQFFQw5YU8y9gQrWIl262TdgnEcXWs0Bd_f1dDo/edit?tab=t.0#heading=h.y6jfis3ouryn).

## End-to-end example

Replace `HOST`, `KEY`, and the image path with real values. This is the whole
upload path (steps 1–3); step 4 happens later when the device posts its event.

```bash
HOST="https://mo-08942879d73e42cfb4f5fc48690e9775.ecs.us-east-2.on.aws"
KEY="<device_key>"
EVENT_ID="evt_2026_01_31_0007"

# 1-2. Ask for an upload URL.
RESP=$(curl -s -X POST "$HOST/v1/snapshots/upload-url" \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d "{\"event_id\":\"$EVENT_ID\"}")
echo "$RESP"
# => {"upload_url":"https://moo-snapshots-prod.s3...","key":"snapshots/<farm_id>/evt_2026_01_31_0007.jpg","ttl_seconds":300}

UPLOAD_URL=$(echo "$RESP" | python3 -c 'import sys,json; print(json.load(sys.stdin)["upload_url"])')
KEY_PATH=$(echo "$RESP"   | python3 -c 'import sys,json; print(json.load(sys.stdin)["key"])')

# 3. Upload the bytes (no auth header, no Content-Type).
curl -s -o /dev/null -w '%{http_code}\n' -X PUT "$UPLOAD_URL" --data-binary @snapshot.jpg
# => 200

# 4. Later, reference KEY_PATH as snapshot.url in the event payload.
echo "snapshot.url = $KEY_PATH"
```

Expected status codes: `200` on a good key, `401` on a missing/bad key, `422`
on a malformed `event_id`, `403` on a PUT after the URL's TTL expires.

## Reference values

| Item | Value |
|---|---|
| Backend host | `https://<express-host>.ecs.us-east-2.on.aws` (HTTPS) |
| Bucket | `moo-snapshots-prod` (private; reachable only via signed URLs) |
| Region | `us-east-2` |
| Key layout | `snapshots/{farm_id}/{event_id}.jpg` (`farm_id` is a UUID) |
| URL TTL | 300s (default) |
| Upload method | HTTP `PUT` of raw bytes, no extra headers |
| Canonical reference | the `key` returned by the upload-URL endpoint |
