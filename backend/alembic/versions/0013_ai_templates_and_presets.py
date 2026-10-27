"""Add AI reverse templates and creation presets tables

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-27

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. ai_reverse_templates 表：视觉反推模板
    op.create_table(
        "ai_reverse_templates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=True),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("user_prompt_template", sa.Text(), nullable=True),
        sa.Column("is_builtin", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("default_model_profile_id", sa.Integer(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["default_model_profile_id"], ["ai_model_profiles.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_ai_reverse_templates_code"),
    )
    op.create_index("ix_ai_reverse_templates_enabled", "ai_reverse_templates", ["enabled"])
    op.create_index("ix_ai_reverse_templates_is_builtin", "ai_reverse_templates", ["is_builtin"])

    # 2. ai_creation_presets 表：创作预设（生图/编辑/Prompt优化规范）
    op.create_table(
        "ai_creation_presets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=True),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("creation_mode", sa.String(length=32), nullable=False, server_default="image_generate"),
        sa.Column("system_rules", sa.Text(), nullable=False),
        sa.Column("default_model_profile_id", sa.Integer(), nullable=True),
        sa.Column("default_params_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("is_builtin", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["default_model_profile_id"], ["ai_model_profiles.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_ai_creation_presets_code"),
        sa.CheckConstraint(
            "creation_mode IN ('image_generate', 'image_edit')",
            name="ck_ai_creation_presets_mode",
        ),
    )
    op.create_index("ix_ai_creation_presets_enabled", "ai_creation_presets", ["enabled"])
    op.create_index("ix_ai_creation_presets_is_builtin", "ai_creation_presets", ["is_builtin"])


def downgrade() -> None:
    op.drop_index("ix_ai_creation_presets_is_builtin", table_name="ai_creation_presets")
    op.drop_index("ix_ai_creation_presets_enabled", table_name="ai_creation_presets")
    op.drop_table("ai_creation_presets")

    op.drop_index("ix_ai_reverse_templates_is_builtin", table_name="ai_reverse_templates")
    op.drop_index("ix_ai_reverse_templates_enabled", table_name="ai_reverse_templates")
    op.drop_table("ai_reverse_templates")
