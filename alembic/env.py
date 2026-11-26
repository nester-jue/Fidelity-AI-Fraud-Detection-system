"""Alembic environment for NEXA.

The database URL always comes from the running configuration/environment so
CI, local development and production never silently migrate different targets.
"""
import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, engine_from_config, pool

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from backend.app.core.config import settings  # noqa: E402
from backend.app.services.db import get_database_url  # noqa: E402
from backend.app.models import sqlalchemy_models  # noqa: E402,F401

config = context.config
if config.config_file_name and os.path.exists(config.config_file_name):
    try:
        fileConfig(config.config_file_name)
    except Exception:
        pass

target_metadata = sqlalchemy_models.Base.metadata


def _url() -> str:
    return os.getenv("DATABASE_URL") or get_database_url()


def run_migrations_offline():
    context.configure(
        url=_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    url = _url()
    if url.startswith("sqlite"):
        connectable = create_engine(url, poolclass=pool.NullPool)
    else:
        section = dict(config.get_section(config.config_ini_section) or {})
        section["sqlalchemy.url"] = url
        connectable = engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
