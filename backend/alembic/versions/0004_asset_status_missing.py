"""Allow the asset status 'missing' for unavailable external source files.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-24

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # batch mode recreates the table (SQLite cannot drop a CHECK in place)
    with op.batch_alter_table("assets") as batch:
        batch.drop_constraint("ck_assets_status", type_="check")
        batch.create_check_constraint(
            "ck_assets_status", "status IN ('active','trashed','missing')"
        )


def downgrade() -> None:
    with op.batch_alter_table("assets") as batch:
        batch.drop_constraint("ck_assets_status", type_="check")
        batch.create_check_constraint("ck_assets_status", "status IN ('active','trashed')")
