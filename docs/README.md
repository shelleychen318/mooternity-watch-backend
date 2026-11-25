# Documentation

Reference docs for the Moo-ternity Watch backend. Start with the
[project README](../README.md) for an overview and local setup; this folder holds
the deeper reference material you consult for a specific task.

| Document | What it covers |
|---|---|
| [data-model.md](data-model.md) | The PostgreSQL schema: entities, conventions, and how it maps to `app/models/`. |
| [deployment.md](deployment.md) | How the backend runs on AWS (ECS Fargate), plus deploy, migrate, and start/stop operations. |
| [device-integration-contract.md](device-integration-contract.md) | How an edge device authenticates, uploads a snapshot via a presigned URL, and posts a detection event to `POST /v1/events` (payload, dedupe, status codes). |

Related docs elsewhere in the repo:

- [`alembic/README.md`](../alembic/README.md) — writing and reviewing migrations
  (including the Postgres-enum gotcha).

> `logbook.local.md` is a personal, gitignored work log, not shared reference.
