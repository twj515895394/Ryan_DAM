"""Add V2 asset origin and prompt CAS versioning fields to assets table

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-27

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLite ALTER TABLE ADD COLUMN
    with op.batch_alter_table("assets") as batch_op:
        batch_op.add_column(
            sa.Column(
                "asset_origin",
                sa.String(length=32),
                nullable=False,
                server_default="local_import",
            )
        )
        batch_op.add_column(
            sa.Column(
                "prompt_origin",
                sa.String(length=32),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "prompt_revision",
                sa.Integer(),
                nullable=False,
                server_default="1",
            )
        )
        batch_op.add_column(
            sa.Column(
                "generation_task_id",
                sa.String(length=64),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "generation_result_id",
                sa.String(length=64),
                nullable=True,
            )
        )
        batch_op.create_index("ix_assets_asset_origin", ["asset_origin"])
        batch_op.create_index("ix_assets_generation_task_id", ["generation_task_id"])

    # Backfill prompt_origin for existing assets that already have prompt_text
    op.execute(
        "UPDATE assets SET prompt_origin = 'manual' WHERE prompt_text IS NOT NULL AND prompt_origin IS NULL"
    )


def downgrade() -> None:
    with op.batch_alter_table("assets") as batch_op:
        batch_op.drop_index("ix_assets_generation_task_id")
        batch_op.drop_index("ix_assets_asset_origin")
        batch_op.drop_column("generation_result_id")
        batch_op.drop_column("generation_task_id")
        batch_op.drop_column("prompt_revision")
        batch_op.drop_column("prompt_origin")
        batch_op.drop_column("asset_origin")
