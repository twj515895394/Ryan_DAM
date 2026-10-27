"""Add ai_model_profiles and ai_default_bindings tables for V2 AI models and default routing

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-27

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_model_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider_id", sa.Integer(), nullable=False),
        sa.Column("model_id", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("adapter_kind", sa.String(length=32), nullable=False, server_default="openai_standard"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("capabilities_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["provider_id"], ["ai_provider_instances.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_id", "model_id", name="uq_ai_model_profiles_provider_model"),
        sa.CheckConstraint(
            "adapter_kind IN ('openai_standard', 'openai_chat_markdown', 'gemini_standard', 'custom')",
            name="ck_ai_model_profiles_adapter_kind",
        ),
    )
    op.create_index("ix_ai_model_profiles_provider_id", "ai_model_profiles", ["provider_id"])
    op.create_index("ix_ai_model_profiles_enabled", "ai_model_profiles", ["enabled"])

    op.create_table(
        "ai_default_bindings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("capability", sa.String(length=32), nullable=False),
        sa.Column("scene", sa.String(length=64), nullable=False, server_default="global"),
        sa.Column("model_profile_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["model_profile_id"], ["ai_model_profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("capability", "scene", name="uq_ai_default_bindings_cap_scene"),
        sa.CheckConstraint(
            "capability IN ('text_optimize', 'image_understand', 'image_generate', 'image_edit')",
            name="ck_ai_default_bindings_capability",
        ),
    )
    op.create_index("ix_ai_default_bindings_capability", "ai_default_bindings", ["capability"])
    op.create_index("ix_ai_default_bindings_scene", "ai_default_bindings", ["scene"])


def downgrade() -> None:
    op.drop_index("ix_ai_default_bindings_scene", table_name="ai_default_bindings")
    op.drop_index("ix_ai_default_bindings_capability", table_name="ai_default_bindings")
    op.drop_table("ai_default_bindings")

    op.drop_index("ix_ai_model_profiles_enabled", table_name="ai_model_profiles")
    op.drop_index("ix_ai_model_profiles_provider_id", table_name="ai_model_profiles")
    op.drop_table("ai_model_profiles")
