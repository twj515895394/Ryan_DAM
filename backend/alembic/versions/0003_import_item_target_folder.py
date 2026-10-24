"""Add per-item target folder so folder imports can mirror hierarchy.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-24

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE import_job_items ADD COLUMN target_folder_id INTEGER REFERENCES folders (id)")


def downgrade() -> None:
    op.drop_column("import_job_items", "target_folder_id")
