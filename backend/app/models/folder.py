from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base, utcnow


class Folder(Base):
    """Logical folder node; UI trees are built from parent_id, not disk layout."""

    __tablename__ = "folders"
    __table_args__ = (
        CheckConstraint("scope_type IN ('general','project')", name="ck_folders_scope_type"),
        Index("ix_folders_scope_parent", "scope_type", "project_id", "parent_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    scope_type: Mapped[str] = mapped_column(String(16))
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("folders.id"), nullable=True, index=True)
    sort_order: Mapped[int] = mapped_column(default=0)
    locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)
