# CLAUDE.md

Guidance for AI assistants (and humans) working in this repo. Keep it short and
current — update it when conventions change.

## What this is

The **Backend & Systems Integration** subsystem for Moo-ternity Watch (cattle
calving monitoring). It ingests detection events pushed by an edge device,
persists them, runs alert logic, and dispatches notifications, while exposing a
REST + SSE API to the frontend.

**Stack:** Python 3.11+ · FastAPI · PostgreSQL (SQLAlchemy 2.0 + Alembic) ·
S3/MinIO · SSE · Twilio (SMS) · FCM (push) · Docker.

**Work is milestone-driven.** Tasks carry stable milestone/task IDs
(e.g. `M2-T1`) with dependencies, acceptance criteria (ACs), and open
questions. Pick up and reference work by that ID.

## Layout

```
app/
  main.py            FastAPI app factory (create_app) + /health
  config.py          Settings (pydantic-settings, MW_ prefixed env vars)
  db.py              engine, SessionLocal, get_session, Base
  models/            SQLAlchemy ORM — one module per table, re-exported in __init__
  schemas/           Pydantic wire contracts (validation) — separate from models/
alembic/versions/    migrations
tests/               mirrors app/ (tests/models/, tests/schemas/, ...)
scratch/             local-only notes; gitignored, never committed
```

## Commands

```bash
# setup
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install                          # optional

# local services (Postgres on host :5433, S3/MinIO on :9000)
docker compose up -d db s3

# env (point tools at compose Postgres)
export MW_DATABASE_URL="postgresql+psycopg://moo:moo@localhost:5433/mooternity"
export MW_TEST_DATABASE_URL="postgresql+psycopg://moo:moo@localhost:5433/mooternity_test"

# the full local gate — run ALL of these before pushing
ruff check .
ruff format --check .
pytest                                      # full suite
alembic check                               # no model/migration drift

# narrower runs
pytest tests/schemas                        # one area
pytest tests/schemas/test_event.py          # one file

# migrations
alembic upgrade head
alembic revision --autogenerate -m "describe change"

# run the API
uvicorn app.main:app --reload               # curl http://127.0.0.1:8000/health
```

CI (`.github/workflows/ci.yml`) runs exactly: `ruff check` → `ruff format
--check` → `pytest` (with `MW_ENVIRONMENT=test`, no database). Match it locally.

## Conventions

### Code
- `from __future__ import annotations` at the top of every module.
- `enum.StrEnum` for enumerations (see `config.py`, `models/alert.py`).
- Type-hint everything; modern syntax (`X | None`, `list[...]`).
- Ruff is the single linter/formatter (line length 100; rules `E,F,I,UP,B`).
  Let it fix/format; don't hand-format.

### Config
- All settings are env-driven with the **`MW_`** prefix, defined in
  `app/config.py` and read via `get_settings()`. Add new settings there.
- Secrets have no safe default and fail fast in non-local environments. Never
  commit real secrets; `.env` is local-only.

### Tests
- `tests/` mirrors `app/` (a module in `app/schemas/` → `tests/schemas/`).
- **Test the decisions we made, not the framework.** Cover each AC with a
  focused test (a constraint, a unique key, a lifecycle transition, a default) —
  skip tests that merely re-prove that SQLAlchemy/Pydantic work.
- DB-backed tests use the `db_session` fixture (transaction-per-test, rolled
  back) and `make_*` factories in `tests/conftest.py`. They **skip** when no
  database is reachable, so the suite stays green in CI without Postgres. Pure
  logic/validation tests need no DB and run everywhere.
- Scope tests to **behavior, not a frozen snapshot**, when the underlying data
  is expected to change (e.g. test "unmapped type falls back to default", not a
  hardcoded list of every mapping).

### Layering (important)
- **Contract vs. persistence are separate.** `app/schemas/` (Pydantic) validates
  incoming data at the boundary; `app/models/` (SQLAlchemy) persists it. They
  drift on purpose — e.g. `event_type` is a strict enum on the wire but a free
  string in the DB column; `received_timestamp` is null on the wire and
  server-stamped on ingestion. Don't collapse the two layers.
- Keep `app/schemas/` free of SQLAlchemy imports.

## Migrations & the Postgres-enum gotcha

- Autogenerate is a draft — **always review** the generated migration.
- Alembic creates native enum types on `upgrade` but does **not** drop them on
  `downgrade`. For any migration adding an enum column, add explicit enum-type
  drops in `downgrade()` so the up/down cycle is repeatable.
- Run `alembic check` to confirm models and migrations agree (no drift).
- Prefer adding a new migration over editing one that has run in a shared
  environment.

## Git & PR workflow

- Branch off the latest `main`: `git checkout main && git pull && git checkout
  -b feature/<slug>`. Never commit straight to `main`.
- Commit messages: `Milestone N: <topic>` for milestone work, imperative mood
  otherwise; short bullet body summarizing the change.
- Stage specific paths (e.g. `git add app/schemas tests/schemas`) — not
  `git add .` — so gitignored `scratch/` and stray files stay out.
- PRs target `main`. Style (see PRs #1, #2): sentence-case title; sections
  **Summary / What's added / Notable design points / Testing / How to verify**.
  Keep prose focused on behavior; no milestone IDs in the PR body.
- Write PR body paragraphs and bullets as **single unwrapped lines** — don't
  hard-wrap mid-sentence. GitHub soft-wraps to the full width; hard wrapping
  renders cramped/early-indented. (Code fences keep their own line breaks.)
- After pushing, watch CI: `gh pr checks <n> --watch`. On failure, pull logs
  with `gh run view <run-id> --log-failed` and fix the root cause.

## Known gotchas (learned the hard way)

- **Re-run the full gate after *every* edit, including docstring/comment-only
  changes.** A format-only diff introduced after an earlier green check will
  fail CI. The last thing before pushing is always `ruff format --check .`.
- **Ruff version skew.** pre-commit pins an older ruff (`v0.6.9`) than CI
  installs (latest, e.g. `0.17.3`), and newer ruff reformats things the older
  one left alone (e.g. collapsing a two-line docstring to one line). Trust
  `ruff format .` from the project `.venv` and match CI; don't rely on the
  pre-commit hook alone to catch format issues.
- **Compose Postgres is on host port 5433**, not 5432, to avoid colliding with a
  local Postgres. The default `MW_DATABASE_URL` points at 5432, so export the
  5433 URLs (above) when running tests/migrations against compose.
- **`metadata` is reserved** on SQLAlchemy's declarative base — the `events`
  column is mapped as the Python attribute `event.meta`.

## When adding a feature

1. Read the task + ACs for the milestone/task ID you're implementing; note its
   dependencies and any open questions it touches.
2. Read the neighboring code first; match existing patterns (enums, mixins,
   module-per-table, contract/persistence split).
3. Implement in the right layer; add focused tests per AC.
4. Run the full local gate (`ruff check`, `ruff format --check`, `pytest`,
   `alembic check` if models changed).
5. Branch, commit specific paths, push, open a PR targeting `main`, and confirm
   CI is green.
```

## PR format

Branch off `main`; name branches `<type>/<short-slug>` (e.g. `feat/m2-event-payload-contract`, `chore/move-tasks-to-local-scratch`).

**Title:** `<type>: <description>` (Conventional Commits). Lowercase description, no trailing period, optional parenthetical scope clarifier.

- `feat:` new capability · `fix:` bug fix · `docs:` docs only · `chore:` tooling/housekeeping · `refactor:` · `test:` · `ci:`
- Example: `feat: event payload contract (versioned schema, validation + classification)`

**Body:** Markdown sections, in this order, including only the ones that apply:

1. `## Summary` — always. 2–4 sentences: what it adds/changes and where it sits in the pipeline.
2. `## What's added` / `## What's changed` — table when introducing multiple modules/entities, else bullets.
3. `## Notable design points` — when there are non-obvious decisions. Bullets with a **bold lead-in** per point.
4. `## Migrations` — when models/schema change; note `alembic check` drift status.
5. `## Testing` — when code changes; what's covered, where tests live, DB-required or not.
6. `## How to verify` — when the reviewer can run something; a fenced command block.
7. `## Verification Results` — when there's output/screenshots.
8. `## Notes` — caveats, scope limits, "docs-only, no CI impact."

Keep docs/config-only PRs lean: Summary + What's changed + Notes is usually enough.
