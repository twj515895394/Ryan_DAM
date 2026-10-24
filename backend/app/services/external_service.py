"""External directory linking and scanning (tickets 17-19).

External sources are read-only mirrors of directories on disk: scanning only
reads files, indexes metadata and mirrors the sub-directory hierarchy into the
library. It NEVER writes to, moves or deletes source files — the scan result
for vanished files is a 'missing' status on the index row, not a deletion.
"""

from __future__ import annotations

import mimetypes
import os
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.core.errors import ApiError
from backend.app.models.asset import Asset
from backend.app.models.external_source import ExternalSource
from backend.app.services.folder_service import ensure_folder_path, get_folder_or_404
from backend.app.services.import_service import guess_asset_type


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _normalize_root(root_path: str) -> Path:
    cleaned = root_path.strip().strip('"').strip("'")
    if not cleaned:
        raise ApiError("validation_error", "外部目录路径不能为空。", 422)
    path = Path(os.path.abspath(cleaned))
    if not path.is_dir():
        raise ApiError("source_unavailable", f"目录不存在或不可访问：{cleaned}", 404)
    return path


def get_source_or_404(db: Session, source_id: int) -> ExternalSource:
    source = db.get(ExternalSource, source_id)
    if source is None:
        raise ApiError("not_found", "外部目录不存在或已被解除关联。", 404)
    return source


def create_external_source(
    db: Session, *, root_path: str, target_folder_id: int, display_name: str | None = None
) -> tuple[ExternalSource, dict[str, int]]:
    root = _normalize_root(root_path)
    get_folder_or_404(db, target_folder_id)
    duplicate = db.scalar(
        select(ExternalSource).where(func.lower(ExternalSource.root_path) == str(root).lower())
    )
    if duplicate is not None:
        raise ApiError("duplicate_name", f"该目录已关联过：{duplicate.root_path}", 409)

    source = ExternalSource(
        root_path=str(root),
        display_name=(display_name or "").strip() or root.name,
        target_folder_id=target_folder_id,
        status="active",
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    stats = scan_external_source(db, source)
    return source, stats


def scan_external_source(db: Session, source: ExternalSource) -> dict[str, int]:
    """Rescan the source directory: add new files, update changed sizes, mark
    vanished files missing and reactivate ones that came back."""
    root = Path(source.root_path)
    if not root.is_dir():
        raise ApiError("source_unavailable", f"源目录不可访问：{source.root_path}", 404)
    target = get_folder_or_404(db, source.target_folder_id)

    indexed = db.scalars(
        select(Asset).where(
            Asset.external_source_id == source.id,
            Asset.status.in_(("active", "missing")),
        )
    ).all()
    by_relpath: dict[str, Asset] = {}
    for asset in indexed:
        try:
            rel = os.path.relpath(asset.file_path, str(root)).replace("\\", "/").lower()
        except ValueError:
            rel = None  # file recorded on another drive than the root
        if rel is not None:
            by_relpath[rel] = asset

    seen: set[str] = set()
    added = updated = reactivated = 0
    for dirpath, _dirnames, filenames in os.walk(root):
        for filename in filenames:
            full = Path(dirpath) / filename
            try:
                stat = full.stat()
            except OSError:
                continue  # unreadable entry: skip it instead of failing the scan
            rel = os.path.relpath(str(full), str(root)).replace("\\", "/")
            key = rel.lower()
            seen.add(key)
            asset = by_relpath.get(key)
            if asset is None:
                parent = Path(rel).parent
                parts = [] if str(parent) == "." else list(parent.parts)
                folder = ensure_folder_path(db, base=target, parts=parts)
                asset_type = guess_asset_type(full)
                db.add(
                    Asset(
                        folder_id=folder.id,
                        name=filename,
                        extension=full.suffix.lstrip(".") or None,
                        mime_type=mimetypes.guess_type(filename)[0],
                        asset_type=asset_type,
                        size_bytes=stat.st_size,
                        file_path=str(full),
                        source_type="external",
                        external_source_id=source.id,
                        thumbnail_status="ready" if asset_type in ("document", "other") else "pending",
                    )
                )
                added += 1
            else:
                if asset.size_bytes != stat.st_size:
                    asset.size_bytes = stat.st_size
                    asset.updated_at = _utcnow()
                    updated += 1
                if asset.status == "missing":
                    asset.status = "active"
                    reactivated += 1

    missing = 0
    for key, asset in by_relpath.items():
        if key not in seen and asset.status != "missing":
            asset.status = "missing"
            missing += 1
    source.last_scan_at = _utcnow()
    db.commit()
    return {"added": added, "updated": updated, "missing": missing, "reactivated": reactivated}


def list_external_sources(db: Session) -> list[dict]:
    counts = dict(
        db.execute(
            select(Asset.external_source_id, func.count(Asset.id))
            .where(Asset.source_type == "external", Asset.status.in_(("active", "missing")))
            .group_by(Asset.external_source_id)
        ).all()
    )
    missing_counts = dict(
        db.execute(
            select(Asset.external_source_id, func.count(Asset.id))
            .where(Asset.source_type == "external", Asset.status == "missing")
            .group_by(Asset.external_source_id)
        ).all()
    )
    from backend.app.models.folder import Folder

    rows = (
        db.query(ExternalSource, Folder.name)
        .outerjoin(Folder, ExternalSource.target_folder_id == Folder.id)
        .order_by(ExternalSource.id)
        .all()
    )
    return [
        {
            "id": source.id,
            "root_path": source.root_path,
            "display_name": source.display_name,
            "target_folder_id": source.target_folder_id,
            "target_folder_name": folder_name,
            "last_scan_at": source.last_scan_at,
            "status": source.status,
            "asset_count": counts.get(source.id, 0),
            "missing_count": missing_counts.get(source.id, 0),
        }
        for source, folder_name in rows
    ]


def unlink_external_source(db: Session, source_id: int) -> int:
    """Remove the link and every index row that is STILL external.

    Assets already converted to managed keep their records (business
    invariant); source files on disk are never touched.
    """
    from backend.app.services.trash_service import delete_asset_index

    source = get_source_or_404(db, source_id)
    external_assets = db.scalars(
        select(Asset).where(
            Asset.external_source_id == source.id,
            Asset.source_type == "external",
        )
    ).all()
    for asset in external_assets:
        delete_asset_index(db, asset)
    db.delete(source)
    db.commit()
    return len(external_assets)
