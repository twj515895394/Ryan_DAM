from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base, utcnow


class Asset(Base):
    """One stable record per asset; file_path always holds the real file location."""

    __tablename__ = "assets"
    __table_args__ = (
        CheckConstraint("source_type IN ('managed','external')", name="ck_assets_source_type"),
        CheckConstraint("asset_type IN ('image','video','audio','document','other')", name="ck_assets_asset_type"),
        CheckConstraint("status IN ('active','trashed','missing')", name="ck_assets_status"),
        CheckConstraint(
            "asset_origin IN ('local_import', 'ai_generated', 'ai_edited')",
            name="ck_assets_asset_origin",
        ),
        CheckConstraint(
            "prompt_origin IS NULL OR prompt_origin IN ('manual', 'ai_reverse', 'generation_prompt', 'edit_prompt')",
            name="ck_assets_prompt_origin",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    folder_id: Mapped[int | None] = mapped_column(ForeignKey("folders.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    extension: Mapped[str | None] = mapped_column(String(64), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    asset_type: Mapped[str] = mapped_column(String(16), default="other")
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    file_path: Mapped[str] = mapped_column(Text)
    source_type: Mapped[str] = mapped_column(String(16))
    external_source_id: Mapped[int | None] = mapped_column(ForeignKey("external_sources.id"), nullable=True, index=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    prompt_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # V2 Origins & Prompt CAS Revision
    asset_origin: Mapped[str] = mapped_column(String(32), default="local_import", index=True)
    prompt_origin: Mapped[str | None] = mapped_column(String(32), nullable=True)
    prompt_revision: Mapped[int] = mapped_column(Integer, default=1)
    generation_task_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    generation_result_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    media_width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    media_height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    media_duration_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    thumbnail_status: Mapped[str] = mapped_column(String(16), default="pending")
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)
    original_folder_id: Mapped[int | None] = mapped_column(ForeignKey("folders.id"), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)
