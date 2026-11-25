# Migrations

Database schema changes are managed with [Alembic](https://alembic.sqlalchemy.org/).
Migration scripts live in [`versions/`](versions).

## Common commands

```bash
export MW_DATABASE_URL="postgresql+psycopg://moo:moo@localhost:5433/mooternity"
alembic upgrade head                                   # apply all migrations
alembic revision --autogenerate -m "describe change"   # generate a new migration
alembic check                                          # confirm models & migrations agree (no drift)
```

Run `alembic check` after autogenerating; it fails if the models and the applied
migrations have drifted.

## Postgres enums: review `downgrade()`

Alembic autogenerate creates native enum types on `upgrade` but **does not drop
them on `downgrade`**. A migration that adds a native enum column must therefore
drop those enum types explicitly in `downgrade()`, or the full up/down cycle is
not repeatable (re-running `upgrade` fails because the type already exists).

When you autogenerate a migration that touches enums (`alerts.status`,
`notifications.status`, `notifications.channel`, or any new one), review the
generated `downgrade()` and add the matching type drops. Existing migrations under
`versions/` show the pattern.

See [`docs/data-model.md`](../docs/data-model.md) for the schema these migrations
build.
