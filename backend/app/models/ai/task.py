from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base, utcnow


class AiTask(Base):
    """AI 执行任务表（文生图、图生图编辑、批量反推、提示词优化）。"""

    __tablename__ = "ai_tasks"
    __table_args__ = (
        CheckConstraint(
            "task_type IN ('image_generate', 'image_edit', 'batch_reverse', 'prompt_optimize')",
            name="ck_ai_tasks_task_type",
        ),
        CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'partial_failed', 'failed', 'cancel_requested', 'canceled', 'recovery_needed')",
            name="ck_ai_tasks_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    task_type: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("ai_provider_instances.id", ondelete="SET NULL"), nullable=True, index=True
    )
    model_profile_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("ai_model_profiles.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), default="queued", nullable=False, index=True)
    retry_of: Mapped[str | None] = mapped_column(String(64), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    prompt_final: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_user_request: Mapped[str | None] = mapped_column(Text, nullable=True)
    preset_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("ai_creation_presets.id", ondelete="SET NULL"), nullable=True
    )
    params_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    external_handle: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    progress_pct: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    provider = relationship("AiProviderInstance", foreign_keys=[provider_id])
    model_profile = relationship("AiModelProfile", foreign_keys=[model_profile_id])
    preset = relationship("AiCreationPreset", foreign_keys=[preset_id])

    items = relationship("AiTaskItem", back_populates="task", cascade="all, delete-orphan")
    references = relationship("AiTaskReference", back_populates="task", cascade="all, delete-orphan")
    results = relationship("AiResult", back_populates="task", cascade="all, delete-orphan")

    @property
    def params(self) -> dict[str, Any]:
        try:
            return json.loads(self.params_json) if self.params_json else {}
        except Exception:
            return {}

    @params.setter
    def params(self, value: dict[str, Any]) -> None:
        self.params_json = json.dumps(value, ensure_ascii=False)


class AiTaskItem(Base):
    """AI 任务的子项（用于批量反推逐项审核与细粒度结果记录）。"""

    __tablename__ = "ai_task_items"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'succeeded', 'failed', 'committed', 'skipped')",
            name="ck_ai_task_items_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("ai_tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    asset_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("assets.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False, index=True)
    draft_prompt_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_revision_at_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )

    task = relationship("AiTask", back_populates="items")
    asset = relationship("Asset", foreign_keys=[asset_id])


class AiTaskReference(Base):
    """输入参考图的不可变快照记录。"""

    __tablename__ = "ai_task_references"
    __table_args__ = (
        CheckConstraint(
            "source_kind IN ('asset', 'history_result', 'local_upload')",
            name="ck_ai_task_references_source_kind",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("ai_tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    seq: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    role: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    snapshot_path: Mapped[str] = mapped_column(String(512), nullable=False)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    task = relationship("AiTask", back_populates="references")


class AiResult(Base):
    """独立永久 AI 生成历史结果。"""

    __tablename__ = "ai_results"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    task_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("ai_tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    idx: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    history_file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(64), default="image/png", nullable=False)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    imported_asset_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("assets.id", ondelete="SET NULL"), nullable=True, index=True
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False, index=True)

    task = relationship("AiTask", back_populates="results")
    imported_asset = relationship("Asset", foreign_keys=[imported_asset_id])
