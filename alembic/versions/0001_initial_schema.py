"""Baseline schema: all NEXA enterprise tables.

This revision establishes a versioned starting point for deployments that
were previously created by ``init_db()``. Future schema changes must be added
as new, explicit revisions rather than relying on the conservative startup
column migration.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-11-26
"""
from typing import Sequence, Union

from alembic import op

from backend.app.models.sqlalchemy_models import Base

revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Baseline: create every mapped table in dependency order.
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    # Destructive by design; only use against a disposable database.
    Base.metadata.drop_all(bind=op.get_bind())
