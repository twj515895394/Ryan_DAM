from __future__ import annotations

from datetime import datetime
from sqlalchemy import Boolean, CheckConstraint, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base, utcnow


class AiProviderInstance(Base):
    """Stores configured AI provider connections (OpenAI Compatible, native OpenAI, native Gemini)."""

    __tablename__ = "ai_provider_instances"
    __table_args__ = (
        CheckConstraint(
            "family IN ('openai_compatible', 'openai_native', 'gemini_native')",
            name="ck_ai_provider_instances_family",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    family: Mapped[str] = mapped_column(String(32), default="openai_compatible")
    name: Mapped[str] = mapped_column(String(128))
    base_url: Mapped[str] = mapped_column(String(512))
    credential_ref: Mapped[str] = mapped_column(String(128))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    settings_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)
