# Documentation

Reference docs for the Moo-ternity Watch backend. Start with the
[project README](../README.md) for an overview and local setup; this folder holds
the deeper reference material you consult for a specific task.

| Document | What it covers |
|---|---|
| [data-model.md](data-model.md) | The PostgreSQL schema: entities, conventions, and how it maps to `app/models/`. |
| [deployment.md](deployment.md) | How the backend runs on AWS (ECS Fargate), plus deploy, migrate, and start/stop operations. |

Related docs elsewhere in the repo:

- [`alembic/README.md`](../alembic/README.md) — writing and reviewing migrations
  (including the Postgres-enum gotcha).

> `logbook.local.md` is a personal, gitignored work log, not shared reference.
