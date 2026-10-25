"""Allow folder_id to be nullable for trashed assets whose folder was cascade-deleted.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-25

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("assets") as batch:
        batch.alter_column("folder_id", nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("assets") as batch:
        batch.alter_column("folder_id", nullable=False)
