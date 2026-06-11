"""Alembic migration environment.

Supports both offline (``--sql``) and online migrations. The synchronous
psycopg2 driver is used for migrations (Alembic's migration context is sync);
the application itself uses asyncpg at runtime. The DB URL and the target
metadata are sourced from the application so migrations always match the models.
"""

from __future__ import annotations

import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# Import settings and the full model metadata. Importing app.models registers
# every table on Base.metadata for autogenerate.
from app.config.settings import settings
from app.models import Base  # noqa: F401  (ensures all models are imported)

config = context.config

# Allow overriding the DB URL via env (handy for CI/migration jobs that point at
# a different host); otherwise use the app's sync (psycopg2) DSN.
db_url = os.getenv("ALEMBIC_DB_URL", settings.sync_database_url)
config.set_main_option("sqlalchemy.url", db_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations without a DB connection (emit SQL to stdout)."""
    context.configure(
        url=db_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live database connection."""
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = db_url

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
