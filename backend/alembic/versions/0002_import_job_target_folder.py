"""Add target_folder_id to import_jobs for managed import target.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-24

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLite cannot ALTER-add a table-level FK constraint; an inline REFERENCES
    # clause on ADD COLUMN is supported (nullable column, no default).
    op.execute("ALTER TABLE import_jobs ADD COLUMN target_folder_id INTEGER REFERENCES folders (id)")
    op.add_column(
        "import_jobs",
        sa.Column("allow_duplicates", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("import_jobs", "allow_duplicates")
    op.drop_column("import_jobs", "target_folder_id")
