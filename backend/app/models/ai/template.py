from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base, utcnow


class AiReverseTemplate(Base):
    """AI 视觉提示词反推模板表。"""

    __tablename__ = "ai_reverse_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    code: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    user_prompt_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    default_model_profile_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("ai_model_profiles.id", ondelete="SET NULL"), nullable=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    default_model_profile = relationship("AiModelProfile", foreign_keys=[default_model_profile_id])


class AiCreationPreset(Base):
    """AI 创作场景预设（生成/编辑/Prompt规范）。"""

    __tablename__ = "ai_creation_presets"
    __table_args__ = (
        CheckConstraint(
            "creation_mode IN ('image_generate', 'image_edit')",
            name="ck_ai_creation_presets_mode",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    code: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    creation_mode: Mapped[str] = mapped_column(String(32), default="image_generate", nullable=False)
    system_rules: Mapped[str] = mapped_column(Text, nullable=False)
    default_model_profile_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("ai_model_profiles.id", ondelete="SET NULL"), nullable=True
    )
    default_params_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    default_model_profile = relationship("AiModelProfile", foreign_keys=[default_model_profile_id])

    @property
    def default_params(self) -> dict[str, Any]:
        try:
            return json.loads(self.default_params_json) if self.default_params_json else {}
        except Exception:
            return {}

    @default_params.setter
    def default_params(self, value: dict[str, Any]) -> None:
        self.default_params_json = json.dumps(value, ensure_ascii=False)
