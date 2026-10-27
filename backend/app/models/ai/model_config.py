from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base, utcnow


class AiModelProfile(Base):
    """Stores model configurations and capability schemas belonging to a provider instance."""

    __tablename__ = "ai_model_profiles"
    __table_args__ = (
        UniqueConstraint("provider_id", "model_id", name="uq_ai_model_profiles_provider_model"),
        CheckConstraint(
            "adapter_kind IN ('openai_standard', 'openai_chat_markdown', 'gemini_standard', 'custom')",
            name="ck_ai_model_profiles_adapter_kind",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    provider_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("ai_provider_instances.id", ondelete="CASCADE"), nullable=False, index=True
    )
    model_id: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    adapter_kind: Mapped[str] = mapped_column(String(32), default="openai_standard")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    # Capability configuration & schemas:
    # {"text_optimize": {...}, "image_understand": {...}, "image_generate": {...}, "image_edit": {...}}
    capabilities_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)

    # Relationship to provider
    provider = relationship("AiProviderInstance", backref="model_profiles")

    @property
    def capabilities(self) -> dict[str, Any]:
        if not self.capabilities_json:
            return {}
        try:
            return json.loads(self.capabilities_json)
        except Exception:
            return {}

    @capabilities.setter
    def capabilities(self, value: dict[str, Any]) -> None:
        self.capabilities_json = json.dumps(value, ensure_ascii=False)


class AiDefaultBinding(Base):
    """Stores default model bindings across different capabilities and scenes."""

    __tablename__ = "ai_default_bindings"
    __table_args__ = (
        UniqueConstraint("capability", "scene", name="uq_ai_default_bindings_cap_scene"),
        CheckConstraint(
            "capability IN ('text_optimize', 'image_understand', 'image_generate', 'image_edit')",
            name="ck_ai_default_bindings_capability",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    capability: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    scene: Mapped[str] = mapped_column(String(64), default="global", nullable=False)  # global, general, project etc.
    model_profile_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("ai_model_profiles.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)

    # Relationship to model profile
    model_profile = relationship("AiModelProfile")
