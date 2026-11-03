# Moo-ternity Watch — Backend Implementation Tasks

Derived from the "Software Design Doc" (Backend & Systems Integration subsystem).

Tasks are grouped into milestones ordered so that dependencies generally flow top-to-bottom. Each task has a stable ID (`M<milestone>-T<n>`) used for dependency references.

**Legend**
- **Est.** rough effort: S (≤0.5 day), M (~1 day), L (~2–3 days), XL (~1 week).
- **Deps** list task IDs that should be done first.
- Acceptance criteria are the "definition of done" for the task.

**Tech stack (from design):** Python + FastAPI, PostgreSQL, SQLAlchemy + Alembic, S3 (object storage), SSE via FastAPI StreamingResponse, Twilio (SMS), Firebase Cloud Messaging (push), Docker.

---

## Milestone 0 — Project Foundation & Infrastructure

Scaffolding everything else builds on.

### M0-T1 — Repository & project scaffold
- **Est.** S · **Deps.** none
- Set up Python project (FastAPI app skeleton, dependency management, linting/formatting, pre-commit, basic `pytest` harness).
- **Acceptance**
  - `app` package imports and a `/health` endpoint returns 200.
  - `pytest` runs green on an empty suite; lint/format checks pass in CI.

### M0-T2 — Dockerization & local dev environment
- **Est.** M · **Deps.** M0-T1
- Dockerfile for the API; `docker-compose` with Postgres + a local S3-compatible store (e.g. MinIO) for development.
- **Acceptance**
  - `docker compose up` brings up API + Postgres + object store.
  - API reaches the DB and object store from inside the compose network.

### M0-T3 — Configuration & secrets management
- **Est.** S · **Deps.** M0-T1
- Centralized settings (env-driven): DB URL, S3 creds/bucket, Twilio, FCM, signed-URL TTL, retention window, auth secret.
- **Acceptance**
  - Config loads from environment with validation and sane local defaults.
  - Missing required secrets fail fast with a clear error.

### M0-T4 — Database connection & migration tooling
- **Est.** S · **Deps.** M0-T2, M0-T3
- Wire SQLAlchemy engine/session management and Alembic migrations.
- **Acceptance**
  - Alembic can generate and apply a baseline migration.
  - A session dependency is available to request handlers and is covered by a connectivity test.

---

## Milestone 1 — Data Model & Persistence

The schema the whole pipeline reads/writes. Maps to the design's Data Model section.

### M1-T1 — Core entity tables: FARMS, DEVICES, USERS
- **Est.** M · **Deps.** M0-T4
- Models + migration for `farms`, `devices` (FK farm_id, device_key, last_seen_at), `users` (FK farm_id, name, phone, email, role).
- **Acceptance**
  - Migration creates tables with PK/FK constraints and UUID PKs.
  - CRUD round-trip test passes for each entity.

### M1-T2 — EVENTS table with idempotency key
- **Est.** M · **Deps.** M1-T1
- `events` table: FK farm_id/device, event_type, confidence, jsonb (detections, snapshot, metadata), event_timestamp, received_timestamp. **Unique constraint on `event_id`.**
- **Acceptance**
  - Inserting a duplicate `event_id` raises a unique-violation (verified by test).
  - jsonb columns persist and round-trip nested payloads.

### M1-T3 — ALERTS table with lifecycle states
- **Est.** S · **Deps.** M1-T2
- `alerts` table: FK farm_id/event_id, status (active/acknowledged/resolved), created_at, acknowledged_at, resolved_at.
- **Acceptance**
  - Status transitions persist with their timestamps.
  - FK to events enforced.

### M1-T4 — NOTIFICATIONS table (also serves as job queue)
- **Est.** M · **Deps.** M1-T3, M1-T1
- `notifications` table: FK alert_id/user_id, channel, status (pending→sent/failed), attempts, next_retry_at, last_error, sent_at.
- **Acceptance**
  - Rows can be inserted as `pending` and transitioned to `sent`/`failed`.
  - Indexed for efficient polling of due `pending` rows (`status` + `next_retry_at`).

### M1-T5 — NOTIFICATION_PREFERENCES table
- **Est.** S · **Deps.** M1-T1
- `notification_preferences`: FK user_id, sms_enabled, push_enabled, email_enabled, quiet_hours_start, quiet_hours_end.
- **Acceptance**
  - One-to-one relationship with users enforced; defaults defined for a new user.

---

## Milestone 2 — Event Payload Contract

The versioned contract co-owned by Backend, CV, and Firmware. Front-loaded because ingestion and the Alert Engine both depend on it.

### M2-T1 — Versioned event schema models
- **Est.** M · **Deps.** M0-T1
- Pydantic models for the event payload: `event_id`, `schema_version`, `device_id`, `farm_id`, `event_type` (enum), timestamps, `confidence`, `snapshot` object, `detections[]` (bbox), free-form `metadata`.
- **Acceptance**
  - Valid example payload from the design doc parses successfully.
  - Invalid/missing required fields are rejected with clear validation errors.
  - `event_type` enum covers: `calving_detected`, `cow_detected`, `camera_offline`, `error`.

### M2-T2 — Schema versioning strategy
- **Est.** S · **Deps.** M2-T1
- Handle `schema_version` so the contract can evolve safely (reject/branch on unknown major versions).
- **Acceptance**
  - A known version parses; an unsupported version is rejected with an actionable message.
  - Strategy documented inline for CV/Firmware consumers.

### M2-T3 — event_type → handling classification
- **Est.** S · **Deps.** M2-T1
- Map each `event_type` to its handling path: alert-worthy (`calving_detected`), log-only (`cow_detected`), operational (`camera_offline`, `error`).
- **Acceptance**
  - A classifier returns the correct handling path per type, covered by unit tests.

---

## Milestone 3 — Storage Layer

Object storage for snapshots + retention. Maps to the design's Storage component.

### M3-T1 — Object storage client & snapshot references
- **Est.** M · **Deps.** M0-T3
- S3 client wrapper. Snapshots are uploaded by the edge device; backend stores/validates references (URLs) rather than bytes.
- **Acceptance**
  - Can verify/resolve a snapshot object reference against the bucket.
  - Works against local MinIO in dev and S3 config in prod.

### M3-T2 — Signed URL issuance for snapshot retrieval
- **Est.** S · **Deps.** M3-T1
- Generate short-lived signed URLs for snapshot images; TTL from config.
- **Acceptance**
  - Issued URL fetches the object before expiry and fails after.
  - TTL is configurable; default documented.

### M3-T3 — Retention policy / purge job
- **Est.** M · **Deps.** M1-T2, M3-T1
- Configurable-window purge of old events and snapshots.
- **Acceptance**
  - A scheduled/triggerable job deletes events + associated snapshot objects older than the window.
  - Dry-run mode logs what would be deleted without deleting.
  - NOTE: retention window value is an open question — see Open Questions.

---

## Milestone 4 — Ingestion API

Authenticated entry point for edge events. Maps to the Ingestion API component. Depends on the schema, events table, and classification.

### M4-T1 — Device authentication for ingestion
- **Est.** M · **Deps.** M0-T1, M1-T1
- Authenticate edge devices on the ingestion endpoint (per-device key/credential over HTTPS).
- **Acceptance**
  - Requests with a valid device credential are accepted; invalid/missing are 401/403.
  - Credentials are not logged.

### M4-T2 — POST /v1/events endpoint with schema validation
- **Est.** M · **Deps.** M2-T1, M4-T1, M1-T2
- Accept detection events, validate against versioned schema, persist all events.
- **Acceptance**
  - Valid payloads return success and create an `events` row.
  - Invalid payloads return a 4xx with validation detail.

### M4-T3 — Idempotent dedupe by event_id
- **Est.** S · **Deps.** M4-T2, M1-T2
- Dedupe on `event_id` so retried/delayed edge pushes don't double-process.
- **Acceptance**
  - Re-posting the same `event_id` is a no-op success (not a duplicate row, not an error).

### M4-T4 — Server-side received_timestamp & out-of-order tolerance
- **Est.** S · **Deps.** M4-T2
- Stamp `received_timestamp` server-side; do not trust device clocks for ordering; tolerate late/out-of-order events.
- **Acceptance**
  - `received_timestamp` is always set server-side regardless of payload.
  - Late/out-of-order events persist without error and are ordered by server time where ordering matters.

### M4-T5 — Forward alert-worthy events to Alert Engine
- **Est.** S · **Deps.** M4-T2, M2-T3
- Route persisted events: alert-worthy → Alert Engine; others logged/handled per classification.
- **Acceptance**
  - `calving_detected` triggers the Alert Engine path; `cow_detected` is log-only; operational types are handled as operational.

---

## Milestone 5 — Alert Engine

Alert lifecycle + debounce + async notification handoff. Depends on ingestion forwarding and the alerts/notifications tables.

### M5-T1 — Alert creation from events
- **Est.** M · **Deps.** M4-T5, M1-T3
- Create an alert from an alert-worthy event (status `active`).
- **Acceptance**
  - An alert-worthy event produces one `alerts` row linked to the event.
  - Runs synchronously within the ingestion request up to persisting the alert.

### M5-T2 — Debounce / cooldown logic
- **Est.** L · **Deps.** M5-T1
- A single calving event stream produces a single alert thread (debounce/cooldown window).
- **Acceptance**
  - Multiple events within the cooldown window for the same device/animal collapse into one alert thread.
  - Window is configurable; behavior covered by tests for both within- and outside-window cases.
  - NOTE: depends on CV emitting single vs. streamed events — see Open Questions.

### M5-T3 — Alert lifecycle transitions
- **Est.** S · **Deps.** M5-T1
- Manage active → acknowledged → resolved with timestamps.
- **Acceptance**
  - Valid transitions persist and set the right timestamp; invalid transitions are rejected.

### M5-T4 — Async notification handoff (enqueue pending rows)
- **Est.** M · **Deps.** M5-T1, M1-T4, M1-T5
- After persisting an alert, enqueue notification work by inserting `pending` rows into `notifications` — resolved against each recipient's preferences.
- **Acceptance**
  - A new alert inserts `pending` notification rows for the right recipients/channels per preferences (respecting quiet hours).
  - Handoff is asynchronous — the ingestion request does not block on sending.

### M5-T5 — Escalation / re-notify on unacknowledged alerts
- **Est.** M · **Deps.** M5-T3, M5-T4
- Optional: re-notify if an alert stays unacknowledged past a timeout.
- **Acceptance**
  - An unacknowledged alert past the timeout enqueues a follow-up notification.
  - Acknowledged alerts do not escalate. Timeout configurable. (Flagged optional in the design.)

---

## Milestone 6 — Notification Service

Channel-agnostic dispatcher + background worker. Depends on notifications queue and preferences.

### M6-T1 — Channel-agnostic dispatcher with pluggable senders
- **Est.** M · **Deps.** M1-T4
- Dispatcher interface with pluggable senders; resolve recipients/channels from preferences.
- **Acceptance**
  - A new sender can be registered without changing dispatcher code.
  - Dispatcher selects channels based on a user's enabled preferences.

### M6-T2 — SMS sender (Twilio, primary channel)
- **Est.** M · **Deps.** M6-T1, M0-T3
- Implement the SMS sender via Twilio.
- **Acceptance**
  - A pending SMS notification sends via Twilio (mocked in tests) and updates status to `sent`.
  - Twilio errors map to transient vs. permanent failure handling.

### M6-T3 — Push sender (Firebase Cloud Messaging, secondary)
- **Est.** M · **Deps.** M6-T1, M0-T3
- Implement the push sender via FCM.
- **Acceptance**
  - A pending push notification sends via FCM (mocked in tests) and updates status.
  - Missing/invalid device token handled gracefully.

### M6-T4 — Background worker: poll pending notifications
- **Est.** L · **Deps.** M6-T1, M1-T4
- Worker that continuously polls `notifications` for due `pending` rows, dispatches via the right channel, and updates status.
- **Acceptance**
  - Worker picks up `pending` rows, sends, and sets `sent`/`failed` with `sent_at`.
  - Safe under concurrency (a row is claimed by only one worker instance).

### M6-T5 — Retry with backoff for transient failures
- **Est.** M · **Deps.** M6-T4
- Use `attempts`, `next_retry_at`, `last_error` to retry transient failures with backoff and a max-attempt cap.
- **Acceptance**
  - Transient failures schedule a retry via `next_retry_at`; `attempts` increments and `last_error` is recorded.
  - After max attempts the row is `failed` and not retried further.

---

## Milestone 7 — Frontend API

REST + real-time surface for the app. Maps to the Frontend API component and API Surface table.

### M7-T1 — User authentication (POST /v1/auth/login)
- **Est.** M · **Deps.** M1-T1
- User login issuing a session/token for subsequent requests.
- **Acceptance**
  - Valid credentials return a token; invalid return 401.
  - Protected endpoints reject missing/expired tokens.

### M7-T2 — Multi-tenancy enforcement (farm scoping)
- **Est.** M · **Deps.** M7-T1, M1-T1
- Scope all data access by the authenticated user's `farm_id` (design chose multi-tenancy from the start).
- **Acceptance**
  - A user cannot read/act on another farm's events, alerts, devices, or users (verified by tests).

### M7-T3 — Alerts endpoints (list, detail, acknowledge, resolve)
- **Est.** L · **Deps.** M7-T2, M5-T3, M3-T2
- `GET /v1/alerts`, `GET /v1/alerts/{id}` (incl. snapshot signed URL), `POST /v1/alerts/{id}/acknowledge`, `POST /v1/alerts/{id}/resolve`.
- **Acceptance**
  - List supports querying/filtering; detail includes a valid signed snapshot URL.
  - Acknowledge/resolve drive the correct lifecycle transitions and timestamps.

### M7-T4 — Event history endpoint (GET /v1/events)
- **Est.** S · **Deps.** M7-T2, M1-T2
- Query event history with lookback.
- **Acceptance**
  - Returns farm-scoped events filtered by time window with pagination.

### M7-T5 — Devices endpoint (GET /v1/devices)
- **Est.** S · **Deps.** M7-T2, M1-T1
- List devices (incl. `last_seen_at`).
- **Acceptance**
  - Returns farm-scoped devices with status/last-seen info.

### M7-T6 — Notification preferences endpoints (GET/PUT /v1/preferences)
- **Est.** M · **Deps.** M7-T2, M1-T5
- Read and update a user's notification preferences (channels, quiet hours).
- **Acceptance**
  - GET returns current prefs; PUT validates and persists updates; changes are honored by M5-T4/M6 routing.

### M7-T7 — Live alert stream (GET /v1/stream via SSE)
- **Est.** L · **Deps.** M7-T2, M5-T1
- Server-Sent Events stream that pushes new alerts into an open app in real time (FastAPI StreamingResponse).
- **Acceptance**
  - A connected client receives a new alert event within seconds of creation.
  - Stream is farm-scoped and handles client disconnects/reconnects cleanly.

---

## Milestone 8 — Cross-Cutting & Hardening

### M8-T1 — Operational event handling (camera_offline, error)
- **Est.** M · **Deps.** M4-T5, M6-T1
- Handle operational events: notify producer on `camera_offline`; log + ops monitoring on `error`.
- **Acceptance**
  - `camera_offline` produces a producer notification; `error` is logged and surfaced to ops monitoring.

### M8-T2 — Observability (logging, metrics, tracing)
- **Est.** M · **Deps.** M0-T1
- Structured logging, basic metrics (ingestion rate, alert counts, notification success/fail), request tracing.
- **Acceptance**
  - Key pipeline stages emit structured logs + metrics; a dashboard/queryable source exists for send success/failure.

### M8-T3 — End-to-end integration test (edge push → notification)
- **Est.** L · **Deps.** M4-T5, M5-T4, M6-T4, M7-T7
- Full-pipeline test: simulated edge event → ingestion → alert → notification enqueue → worker send → SSE delivery.
- **Acceptance**
  - A `calving_detected` event flows end-to-end, producing one alert, a sent notification, and an SSE push to a connected client.

### M8-T4 — API documentation
- **Est.** S · **Deps.** M4-T2, M7-T1
- Expose/curate OpenAPI docs for all endpoints; document the device-facing event contract for CV/Firmware.
- **Acceptance**
  - OpenAPI spec is served and covers the full API Surface; the event schema is documented for co-owners.

---

## Dependency Summary (critical path)

```
M0 (foundation)
  └─> M1 (data model) ──┐
  └─> M2 (event schema) ┤
  └─> M3 (storage)      │
                        ├─> M4 (ingestion)
                        │      └─> M5 (alert engine)
                        │             └─> M6 (notification service)
                        │             └─> M7 (frontend API, needs M3 signed URLs + M5)
                        └────────────────────> M8 (cross-cutting / hardening, last)
```

Rough critical path: **M0 → M1/M2/M3 → M4 → M5 → M6/M7 → M8.** M2 (schema) should start early since M4 and M5 both block on it. M6 and M7 can largely proceed in parallel once M5 exists.

---

## Open Questions (carried from the design doc — resolve before/while implementing affected tasks)

1. **Data retention period** for events and snapshots — blocks final behavior of **M3-T3**.
2. **CV event emission model** — one event at first sign of calving vs. a stream of events throughout. Directly affects debounce/cooldown design in **M5-T2** (and possibly alert threading).
3. **Confirm the event payload schema** with CV + Firmware — affects **M2-T1/M2-T2** and anything downstream of the contract.

### Additional items I'd flag (not in the doc, worth deciding)
- Authn/authz details for devices (M4-T1) and users (M7-T1): token format, rotation, revocation.
- How snapshot URLs are validated/trusted given the edge device uploads directly to object storage (M3-T1) — e.g. restricting to the expected bucket/prefix.
- Concurrency/locking approach for the notification worker (M6-T4) — `SELECT ... FOR UPDATE SKIP LOCKED` vs. another claim mechanism.
- Quiet-hours semantics: suppress-and-drop vs. defer-until-after for notifications (M5-T4 / M7-T6).
