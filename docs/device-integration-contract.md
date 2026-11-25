# Device integration contract (edge device → backend)

How an edge device talks to the backend for each detection. Per detection the
device does two things: (1) upload the snapshot image to object storage via a
short-lived, pre-authorized URL, then (2) post an event — referencing that
image — to the ingestion API. The backend validates and persists the event,
dedupes retries, and stamps the receive time server-side.

The device never holds AWS credentials and never chooses where anything lands:
it uploads to a URL the backend signs, and the backend derives all identity and
storage scoping from the device's credential.

## Flow

```
device ──(1) POST /v1/snapshots/upload-url (Bearer device key)──> backend
device <──(2) { upload_url, key, ttl_seconds } ────────────────── backend
device ──(3) PUT <upload_url>  (raw image bytes, no AWS creds) ──> S3
device ──(4) POST /v1/events  (Bearer device key, snapshot.url = key) ──> backend
device <──(5) 201 { event_id, received_timestamp } ───────────────────── backend
```

Steps 1–3 upload the snapshot; steps 4–5 post the event that references it.

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

- The `device_key` is provisioned out-of-band (an operator seeds it; see the
  deployment doc's device-seeding section) and configured onto the device.
- Send it only over HTTPS. Never place it in a URL or query string.
- A missing, malformed, or unknown credential returns **401**.

**The credential is the device's whole identity.** The backend resolves the farm
and device from the authenticated `device_key`: it derives the snapshot's storage
location from the device's farm, and records the farm and device on every stored
event. The device does not send its farm or device id, and anything of that sort
in an event body is ignored — a device can only ever write under its own farm and
record events as itself.

---

# Snapshot upload

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

---

# Event post

## 4. Post the event

`POST /v1/events`

### Fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `event_id` | string | yes | Device-generated unique id. The dedupe key (see below). The same id used for the matching snapshot upload. |
| `schema_version` | string | yes | `"MAJOR.MINOR"`, e.g. `"1.0"`. The backend accepts any minor within a supported major; an unsupported major or a malformed value returns **422**. |
| `event_type` | string (enum) | yes | One of `calving_detected`, `cow_detected`, `camera_offline`, `error`. Any other value returns **422**. |
| `event_timestamp` | string (ISO 8601) | yes | The device clock reading for the detection. Used for display, not for ordering. |
| `received_timestamp` | string \| null | no | Ignored. The backend always stamps this server-side on ingestion; send `null` or omit it. |
| `confidence` | number \| null | no | Overall confidence, `0..1`. |
| `snapshot` | object \| null | no | Reference to the uploaded image (see shape below). Set `url` to the `key` from step 2. |
| `detections` | array | no | Per-object detections with bounding boxes (see shape below). Defaults to `[]`. |
| `metadata` | object | no | Free-form bag for extra fields (e.g. model version). Defaults to `{}`. |

Unknown top-level fields are ignored, so a newer minor version of the payload
stays compatible with this backend.

`snapshot` object:

| Field | Type | Notes |
|---|---|---|
| `url` | string | The `key` returned by the snapshot upload-URL endpoint (step 2). |
| `width` | int | Pixels, > 0. |
| `height` | int | Pixels, > 0. |
| `format` | string | e.g. `jpeg`. |
| `captured_at` | string (ISO 8601) | When the frame was captured. |

`detections[]` entry:

| Field | Type | Notes |
|---|---|---|
| `label` | string | Class label from the detection model. |
| `confidence` | number | `0..1`. |
| `bbox` | object | `{ x, y, width, height }`, each a fraction of the frame, `0..1`. |

### Request body

```json
{
  "event_id": "evt_01HTX9P5N8K2J7QF3R4W6YABCD",
  "schema_version": "1.0",
  "event_type": "calving_detected",
  "event_timestamp": "2026-02-14T03:21:47.123Z",
  "received_timestamp": null,
  "confidence": 0.92,
  "snapshot": {
    "url": "snapshots/<farm_id>/evt_01HTX9P5N8K2J7QF3R4W6YABCD.jpg",
    "width": 1920,
    "height": 1080,
    "format": "jpeg",
    "captured_at": "2026-02-14T03:21:47.100Z"
  },
  "detections": [
    {
      "label": "calving",
      "confidence": 0.95,
      "bbox": { "x": 0.34, "y": 0.21, "width": 0.28, "height": 0.41 }
    }
  ],
  "metadata": { "model_version": "calving-detector-v2.3" }
}
```

### 5. Response (`201`)

```json
{
  "event_id": "evt_01HTX9P5N8K2J7QF3R4W6YABCD",
  "received_timestamp": "2026-02-14T03:21:48.517Z"
}
```

- `event_id` — echoes the id from the request.
- `received_timestamp` — the server-set ingestion time (UTC). This is the value
  stored on the event; any `received_timestamp` in the request is ignored.

## Idempotency: retries are safe

`event_id` carries a unique constraint, so re-posting the same `event_id` is a
no-op success — no duplicate row, no error. This lets a device retry freely after
a connectivity loss without special handling.

- Both the first post and any retry return **201**.
- A retry echoes the **originally stored** `received_timestamp`, not a new one —
  the server does not re-stamp an event it has already seen. The status code is
  the same either way, so it does not reveal whether the event was already stored.

## Ordering: late and out-of-order events

The device clock (`event_timestamp`) is not trusted for ordering. The backend
stamps `received_timestamp` on ingestion and orders on it; late or out-of-order
events simply persist. There is no ingest-time ordering requirement — a device
may post events in any order.

---

## Status codes

| Code | Endpoint | When |
|---|---|---|
| `200` | upload-url | A presigned URL was minted. |
| `201` | events | Event accepted (fresh insert or a dedupe hit on a repeated `event_id`). |
| `401` | both | Missing, malformed, or unknown `device_key`. |
| `422` | upload-url | `event_id` has disallowed characters or length. |
| `422` | events | Payload failed validation: unsupported/malformed `schema_version`, unknown `event_type`, a missing required field, or an out-of-range value. The body carries the offending detail. |
| `403` | S3 PUT | The presigned URL's TTL expired, or a signed header was added to the PUT. Request a fresh URL. |

## End-to-end example

Replace `HOST`, `KEY`, and the image path with real values. This runs the whole
per-detection path: upload the snapshot, then post the event that references it,
then re-post the identical event to show the retry is a no-op.

```bash
HOST="https://mo-08942879d73e42cfb4f5fc48690e9775.ecs.us-east-2.on.aws"
KEY="<device_key>"
EVENT_ID="evt_2026_02_14_0007"

# 1-2. Ask for an upload URL.
RESP=$(curl -s -X POST "$HOST/v1/snapshots/upload-url" \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d "{\"event_id\":\"$EVENT_ID\"}")
echo "$RESP"
# => {"upload_url":"https://moo-snapshots-prod.s3...","key":"snapshots/<farm_id>/evt_2026_02_14_0007.jpg","ttl_seconds":300}

UPLOAD_URL=$(echo "$RESP" | python3 -c 'import sys,json; print(json.load(sys.stdin)["upload_url"])')
KEY_PATH=$(echo "$RESP"   | python3 -c 'import sys,json; print(json.load(sys.stdin)["key"])')

# 3. Upload the bytes (no auth header, no Content-Type).
curl -s -o /dev/null -w '%{http_code}\n' -X PUT "$UPLOAD_URL" --data-binary @snapshot.jpg
# => 200

# 4. Post the event, referencing KEY_PATH as snapshot.url.
BODY=$(cat <<JSON
{
  "event_id": "$EVENT_ID",
  "schema_version": "1.0",
  "event_type": "calving_detected",
  "event_timestamp": "2026-02-14T03:21:47.123Z",
  "confidence": 0.92,
  "snapshot": {
    "url": "$KEY_PATH",
    "width": 1920, "height": 1080, "format": "jpeg",
    "captured_at": "2026-02-14T03:21:47.100Z"
  },
  "detections": [
    { "label": "calving", "confidence": 0.95,
      "bbox": { "x": 0.34, "y": 0.21, "width": 0.28, "height": 0.41 } }
  ],
  "metadata": { "model_version": "calving-detector-v2.3" }
}
JSON
)
curl -s -X POST "$HOST/v1/events" \
  -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" -d "$BODY"
# => 201 {"event_id":"evt_2026_02_14_0007","received_timestamp":"2026-02-14T03:21:48.517Z"}

# 5. Re-post the identical event: still 201, same received_timestamp, no second row.
curl -s -X POST "$HOST/v1/events" \
  -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" -d "$BODY"
# => 201 {"event_id":"evt_2026_02_14_0007","received_timestamp":"2026-02-14T03:21:48.517Z"}
```

## Verifying your integration

There are three ways to confirm a push worked, from the quickest to the most
authoritative. The request body itself is **not** written to any log — the
database is the system of record — so "did it store?" is answered by the API
response or by the stored row, not by searching logs for the payload.

### 1. The API response (primary check — no AWS access needed)

Everything a device needs to confirm success is in the responses, so this is the
day-to-day integration check:

| Check | Expected | What it proves |
|---|---|---|
| `PUT` to the presigned URL | `200` | S3 stored the object. |
| `POST /v1/events` | `201` with `{event_id, received_timestamp}` | The event was validated, persisted, and stamped server-side. |
| Re-post the identical event | `201`, **same** `received_timestamp` | Dedupe works — no duplicate row. |
| Bad `device_key` | `401` | Auth is enforced. |
| Unknown `event_type` / missing field | `422` with detail | Validation rejects bad payloads. |

### 2. CloudWatch logs (confirms the request reached the app)

The app runs under uvicorn, whose access log writes one line per request (e.g.
`POST /v1/events 201`) to the ECS task's CloudWatch log group
(`/aws/ecs/default/…`). This confirms the request arrived at the container and
which status it returned. It does **not** include the payload body — use it for
"did my request get there and what did it return," not for inspecting content.

### 3. RDS — confirm the row exists (authoritative)

The stored `events` row is the real proof. RDS is **private** (no public
access), so you do not connect from a laptop even with an AWS login — query it
the same way migrations and device seeding run: a one-off Fargate task on the
deployed image with the command overridden (resolve `<current-task-def>`,
`<task-subnet>`, `<task-sg>` per the deployment doc's "One-off tasks" section).
The task's output lands in its CloudWatch log stream.

```bash
aws ecs run-task \
  --cluster default \
  --task-definition <current-task-def> \
  --launch-type FARGATE \
  --count 1 \
  --network-configuration 'awsvpcConfiguration={subnets=[<task-subnet>],securityGroups=[<task-sg>],assignPublicIp=ENABLED}' \
  --overrides '{"containerOverrides":[{"name":"Main","command":["python","-c","from sqlalchemy import select; from app.db import SessionLocal; from app.models import Event; s=SessionLocal(); [print(e.event_id, e.event_type, e.received_timestamp) for e in s.scalars(select(Event).order_by(Event.received_timestamp.desc()).limit(5))]"]}]}' \
  --region us-east-2
```

Watch the task reach `STOPPED` with `exitCode 0` and read the printed rows in its
log stream.

> **Known limitation.** A `201` proves the *event* persisted, and a `PUT 200`
> proves the *image* was stored, but neither proves the stored image is
> retrievable via the `snapshot.url` the event references — that linkage is
> exercised on the read side (serving a signed download URL), which is not built
> yet. For now, `PUT 200` + `POST 201` referencing that key is the closest
> end-to-end signal.

## Reference values

| Item | Value |
|---|---|
| Backend host | `https://<express-host>.ecs.us-east-2.on.aws` (HTTPS) |
| Auth | `Authorization: Bearer <device_key>` |
| Upload endpoint | `POST /v1/snapshots/upload-url` |
| Event endpoint | `POST /v1/events` |
| Bucket | `moo-snapshots-prod` (private; reachable only via signed URLs) |
| Region | `us-east-2` |
| Key layout | `snapshots/{farm_id}/{event_id}.jpg` (`farm_id` is a UUID) |
| URL TTL | 300s (default) |
| Upload method | HTTP `PUT` of raw bytes, no extra headers |
| Canonical snapshot reference | the `key` returned by the upload-URL endpoint |
| Supported `schema_version` major | `1` (any minor) |
| `event_type` values | `calving_detected`, `cow_detected`, `camera_offline`, `error` |
| Event dedupe key | `event_id` (unique; retries are no-op 201s) |
| Receive time | server-stamped; request value ignored |
| Identity | derived from the credential; farm/device not sent by the device |
