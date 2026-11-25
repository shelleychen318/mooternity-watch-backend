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

## Development

### Prerequisites

- Python 3.11+
- Docker (for Postgres + the local S3-compatible object store)

### Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env            # adjust as needed
pre-commit install              # optional: run lint/format on commit
```

### Local services

```bash
docker compose up -d db s3      # Postgres (host :5433) + S3-compatible store (host :9000)
```

The compose Postgres is published on host port **5433** (to avoid colliding with a
local Postgres on 5432); inside the compose network services still reach it at
`db:5432`. The object store is an S3-compatible server with a pre-created
`moo-snapshots` bucket.

### Database migrations

```bash
export MW_DATABASE_URL="postgresql+psycopg://moo:moo@localhost:5433/mooternity"
alembic upgrade head            # apply migrations
alembic revision --autogenerate -m "describe change"   # generate a new migration
```

### Run the API

```bash
export MW_DATABASE_URL="postgresql+psycopg://moo:moo@localhost:5433/mooternity"
uvicorn app.main:app --reload
# health check:
curl http://127.0.0.1:8000/health
```

Or run the full stack (API + Postgres + object store) in containers:

```bash
docker compose up --build
```

### Lint, format, test

```bash
ruff check .
ruff format --check .
pytest                  # full suite
pytest tests/models     # just the data-model tests
```

The test suite uses a **separate database** (`mooternity_test`) so running tests
never touches your dev/app database — the suite creates and drops its own schema.
The compose stack creates `mooternity_test` automatically on first startup; point
the suite at it with `MW_TEST_DATABASE_URL`:

```bash
export MW_TEST_DATABASE_URL="postgresql+psycopg://moo:moo@localhost:5433/mooternity_test"
pytest
```

Database-backed tests skip automatically when the test database is unreachable,
so the suite stays green in CI without a database.

## Data model

Structured data lives in PostgreSQL, modelled with SQLAlchemy under
[`app/models/`](app/models) (one module per table) and created by Alembic
migrations. See [`docs/data-model.md`](docs/data-model.md) for the entities and
conventions, and [`alembic/README.md`](alembic/README.md) for writing migrations.

## Configuration

All settings are environment-driven with the `MW_` prefix (see
[`.env.example`](.env.example) and `app/config.py`). Secrets have no safe
default and fail fast when missing in non-local environments.
