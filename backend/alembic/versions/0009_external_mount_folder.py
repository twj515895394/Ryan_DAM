"""Add external_sources.mount_folder: marks target folders auto-created by the
link flow (the linked disk directory itself becomes a library folder node).

存量关联（0008 之前创建的）保持原语义：内容直接索引进所选目录，
解除关联时不动目录树；mount_folder=false 即代表这种历史行为。

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-25

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("external_sources") as batch:
        batch.add_column(
            sa.Column("mount_folder", sa.Boolean(), nullable=False, server_default=sa.false())
        )


def downgrade() -> None:
    with op.batch_alter_table("external_sources") as batch:
        batch.drop_column("mount_folder")
