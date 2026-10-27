"""Add AI tasks, task items, task references, and ai results tables

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-27

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. ai_tasks 表
    op.create_table(
        "ai_tasks",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("task_type", sa.String(length=32), nullable=False),
        sa.Column("provider_id", sa.Integer(), nullable=True),
        sa.Column("model_profile_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("retry_of", sa.String(length=64), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("prompt_final", sa.Text(), nullable=True),
        sa.Column("raw_user_request", sa.Text(), nullable=True),
        sa.Column("preset_id", sa.Integer(), nullable=True),
        sa.Column("params_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("external_handle", sa.String(length=255), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("progress_pct", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["provider_id"], ["ai_provider_instances.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["model_profile_id"], ["ai_model_profiles.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["preset_id"], ["ai_creation_presets.id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            "task_type IN ('image_generate', 'image_edit', 'batch_reverse', 'prompt_optimize')",
            name="ck_ai_tasks_task_type",
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'partial_failed', 'failed', 'cancel_requested', 'canceled', 'recovery_needed')",
            name="ck_ai_tasks_status",
        ),
    )
    op.create_index("ix_ai_tasks_status", "ai_tasks", ["status"])
    op.create_index("ix_ai_tasks_provider_id", "ai_tasks", ["provider_id"])
    op.create_index("ix_ai_tasks_created_at", "ai_tasks", ["created_at"])
    op.create_index("ix_ai_tasks_idempotency_key", "ai_tasks", ["idempotency_key"])

    # 2. ai_task_items 表（支持批量反推逐项审核与细粒度结果）
    op.create_table(
        "ai_task_items",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("task_id", sa.String(length=64), nullable=False),
        sa.Column("asset_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("draft_prompt_text", sa.Text(), nullable=True),
        sa.Column("prompt_revision_at_start", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["task_id"], ["ai_tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'succeeded', 'failed', 'committed', 'skipped')",
            name="ck_ai_task_items_status",
        ),
    )
    op.create_index("ix_ai_task_items_task_id", "ai_task_items", ["task_id"])
    op.create_index("ix_ai_task_items_status", "ai_task_items", ["status"])

    # 3. ai_task_references 表（输入参考图不可变快照）
    op.create_table(
        "ai_task_references",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("task_id", sa.String(length=64), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("role", sa.String(length=32), nullable=True),
        sa.Column("source_kind", sa.String(length=32), nullable=False),
        sa.Column("source_id", sa.String(length=64), nullable=True),
        sa.Column("snapshot_path", sa.String(length=512), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["task_id"], ["ai_tasks.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "source_kind IN ('asset', 'history_result', 'local_upload')",
            name="ck_ai_task_references_source_kind",
        ),
    )
    op.create_index("ix_ai_task_references_task_id", "ai_task_references", ["task_id"])

    # 4. ai_results 表（独立永久生成历史结果）
    op.create_table(
        "ai_results",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("task_id", sa.String(length=64), nullable=False),
        sa.Column("idx", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("history_file_path", sa.String(length=512), nullable=False),
        sa.Column("mime_type", sa.String(length=64), nullable=False, server_default="image/png"),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("imported_asset_id", sa.Integer(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["task_id"], ["ai_tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["imported_asset_id"], ["assets.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_ai_results_task_id", "ai_results", ["task_id"])
    op.create_index("ix_ai_results_imported_asset_id", "ai_results", ["imported_asset_id"])
    op.create_index("ix_ai_results_is_deleted", "ai_results", ["is_deleted"])
    op.create_index("ix_ai_results_created_at", "ai_results", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_ai_results_created_at", table_name="ai_results")
    op.drop_index("ix_ai_results_is_deleted", table_name="ai_results")
    op.drop_index("ix_ai_results_imported_asset_id", table_name="ai_results")
    op.drop_index("ix_ai_results_task_id", table_name="ai_results")
    op.drop_table("ai_results")

    op.drop_index("ix_ai_task_references_task_id", table_name="ai_task_references")
    op.drop_table("ai_task_references")

    op.drop_index("ix_ai_task_items_status", table_name="ai_task_items")
    op.drop_index("ix_ai_task_items_task_id", table_name="ai_task_items")
    op.drop_table("ai_task_items")

    op.drop_index("ix_ai_tasks_idempotency_key", table_name="ai_tasks")
    op.drop_index("ix_ai_tasks_created_at", table_name="ai_tasks")
    op.drop_index("ix_ai_tasks_provider_id", table_name="ai_tasks")
    op.drop_index("ix_ai_tasks_status", table_name="ai_tasks")
    op.drop_table("ai_tasks")
