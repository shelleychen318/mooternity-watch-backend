# Data model

Structured data lives in PostgreSQL, modelled with SQLAlchemy under
[`app/models/`](../app/models) (one module per table) and created by Alembic
migrations. The entities:

| Table | Purpose |
|-------|---------|
| `farms` | Top-level tenant; everything is scoped to a farm. |
| `devices` | Edge devices (holds `device_key` credential + `last_seen_at`). |
| `users` | Producers/operators; feeds notification recipients. |
| `events` | Every detection pushed by a device (unique `event_id`, JSONB payload). |
| `alerts` | Alert lifecycle: `active → acknowledged → resolved`. |
| `notifications` | Outbound notification queue (`pending → sent/failed`, with retries). |
| `notification_preferences` | Per-user channel settings + quiet hours (one-to-one with a user). |

A few conventions worth knowing when extending the model:

- **UUID primary keys**, generated server-side by Postgres (`gen_random_uuid()`).
- **`events.event_id`** is a device-generated string with a unique constraint —
  it provides database-level idempotency for retried/delayed edge pushes. It is
  distinct from the internal `events.id` UUID.
- **JSONB** columns (`events.detections`, `events.snapshot`, `events.metadata`)
  hold nested, evolving payload sections. The `metadata` column is exposed as the
  Python attribute `event.meta`, because `metadata` is reserved on SQLAlchemy's
  declarative base.
- **Native enum types** back `alerts.status`, `notifications.status`, and
  `notifications.channel`, so invalid values are rejected by the database.
- `notifications` doubles as a job queue and has a composite index on
  `(status, next_retry_at)` for efficient polling of due rows.

## Migrations

Migrations are managed with Alembic. See [`alembic/README.md`](../alembic/README.md)
for how to generate and review them — including the Postgres-enum gotcha that
affects any migration adding a native enum column.
