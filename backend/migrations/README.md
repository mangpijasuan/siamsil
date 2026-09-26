# Application database migrations

These Alembic migrations manage mutable Siamsil product data in PostgreSQL.
They do not modify the immutable SQLite language release.

From `backend/`:

```bash
alembic upgrade head
alembic current
```

Every schema change must include a reversible migration. CI verifies upgrade,
downgrade, and re-upgrade against PostgreSQL.
