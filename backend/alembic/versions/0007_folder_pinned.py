"""Add folders.pinned for the pin-to-top sidebar affordance.

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-25

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("folders") as batch:
        batch.add_column(
            sa.Column("pinned", sa.Boolean(), nullable=False, server_default=sa.false())
        )


def downgrade() -> None:
    with op.batch_alter_table("folders") as batch:
        batch.drop_column("pinned")
