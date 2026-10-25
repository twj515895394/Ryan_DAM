"""Add folders.locked and folders.description for the folder edit dialog.

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-25

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("folders") as batch:
        batch.add_column(
            sa.Column("locked", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch.add_column(sa.Column("description", sa.String(length=2000), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("folders") as batch:
        batch.drop_column("description")
        batch.drop_column("locked")
