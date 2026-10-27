"""Add ai_provider_instances table for multi-provider configuration (OpenAI Compatible, etc.)

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-27

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_provider_instances",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("family", sa.String(length=32), nullable=False, server_default="openai_compatible"),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("base_url", sa.String(length=512), nullable=False),
        sa.Column("credential_ref", sa.String(length=128), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("settings_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "family IN ('openai_compatible', 'openai_native', 'gemini_native')",
            name="ck_ai_provider_instances_family",
        ),
    )
    op.create_index("ix_ai_provider_instances_family", "ai_provider_instances", ["family"])
    op.create_index("ix_ai_provider_instances_enabled", "ai_provider_instances", ["enabled"])


def downgrade() -> None:
    op.drop_index("ix_ai_provider_instances_enabled", table_name="ai_provider_instances")
    op.drop_index("ix_ai_provider_instances_family", table_name="ai_provider_instances")
    op.drop_table("ai_provider_instances")
