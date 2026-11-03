# Moo-ternity Watch — Backend

The **Backend & Systems Integration** subsystem for Moo-ternity Watch, a cattle-calving monitoring system.

This service receives detection events pushed from the edge device, persists them, applies alert logic, and dispatches notifications — while exposing a REST + real-time (SSE) API to the frontend.

## Role in the system

```
edge device ──(event + snapshot URL)──> [ this backend ] ──(REST / SSE)──> frontend app
                                              │
                                              └── object storage (snapshots, signed URLs)
```

The backend integrates with the other subsystems (edge/firmware, CV, frontend) over versioned contracts — primarily the event payload schema and the REST/SSE API surface.

## Tech stack

- **Language / framework:** Python + FastAPI
- **Database:** PostgreSQL (SQLAlchemy + Alembic)
- **Object storage:** S3
- **Real-time:** Server-Sent Events (FastAPI StreamingResponse)
- **Notifications:** Twilio (SMS), Firebase Cloud Messaging (push)
- **Containerization:** Docker

## Documentation

- [`docs/tasks.md`](docs/tasks.md) — granular implementation tasks, milestones, dependencies, and open questions.
