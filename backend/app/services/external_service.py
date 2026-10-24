"""External directory linking and scanning (tickets 17-19).

External sources are read-only mirrors of directories on disk: scanning only
reads files, indexes metadata and mirrors the sub-directory hierarchy into the
library. It NEVER writes to, moves or deletes source files — the scan result
for vanished files is a 'missing' status on the index row, not a deletion.
Converting an asset to managed (ticket 19) copies the file out and updates the
existing record in place; the source file still stays untouched.
"""

from __future__ import annotations

import hashlib
import mimetypes
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.core.errors import ApiError
from backend.app.models.asset import Asset
from backend.app.models.external_source import ExternalSource
from backend.app.services.folder_service import ensure_folder_path, get_folder_or_404
from backend.app.services.import_service import guess_asset_type
from backend.app.services.settings_service import get_managed_root
from backend.app.services.trash_service import get_asset_or_404

CHUNK_SIZE = 1024 * 1024
SPACE_MARGIN_FACTOR = 1.1  # keep in sync with import_service


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _is_within(path: str, ancestor: str) -> bool:
    """True when `path` equals or lives under `ancestor` (case-insensitive on Windows)."""
    try:
        return os.path.commonpath([os.path.normcase(path), os.path.normcase(ancestor)]) == os.path.normcase(ancestor)
    except ValueError:
        return False


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
    managed_root = Path(get_managed_root(db))
    for dirpath, dirnames, filenames in os.walk(root):
        # never index files that belong to the managed storage itself
        # (linking a parent folder of the managed root would otherwise
        #  re-index objects/.trash/.staging and fight the trash pipeline)
        if _is_within(dirpath, str(managed_root)):
            dirnames[:] = []
            continue
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


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(CHUNK_SIZE)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _copy_with_hash(source: Path, destination: Path) -> str:
    digest = hashlib.sha256()
    with open(source, "rb") as src, open(destination, "wb") as dst:
        while True:
            chunk = src.read(CHUNK_SIZE)
            if not chunk:
                break
            digest.update(chunk)
            dst.write(chunk)
    return digest.hexdigest()


def convert_to_managed(db: Session, asset_id: int) -> Asset:
    """Copy the external file into managed storage and update THIS record in
    place — never a second card. The source file is never removed."""
    asset = get_asset_or_404(db, asset_id)
    if asset.source_type != "external":
        raise ApiError("validation_error", "该资产已经是系统托管，无需转换。", 422)
    source = Path(asset.file_path)
    if not source.is_file():
        raise ApiError("content_unavailable", "外部源文件缺失或不可访问，无法转托管。", 404)

    managed_root = Path(get_managed_root(db))
    objects_dir = managed_root / "objects" / str(asset.id)
    staging_dir = managed_root / ".staging" / f"convert-{asset.id}"
    destination = objects_dir / source.name

    try:
        source_size = source.stat().st_size
        try:
            free_bytes = shutil.disk_usage(managed_root).free
        except OSError:
            free_bytes = None  # root not created yet; the copy below will surface real errors
        if free_bytes is not None and free_bytes < int(source_size * SPACE_MARGIN_FACTOR):
            raise ApiError(
                "insufficient_space",
                f"托管磁盘空间不足：需要约 {source_size} 字节，当前剩余 {free_bytes} 字节。",
                400,
            )

        source_hash = _hash_file(source)
        objects_dir.mkdir(parents=True, exist_ok=True)
        staging_dir.mkdir(parents=True, exist_ok=True)
        staged = staging_dir / source.name
        try:
            staged_hash = _copy_with_hash(source, staged)
            if staged_hash != source_hash or staged.stat().st_size != source_size:
                raise ApiError(
                    "copy_verification_failed",
                    "复制校验失败（哈希或大小不一致），资产保持外部状态，可重试。",
                    400,
                )
            os.replace(staged, destination)  # same volume → atomic
        finally:
            shutil.rmtree(staging_dir, ignore_errors=True)

        try:
            asset.source_type = "managed"
            asset.external_source_id = None
            asset.file_path = str(destination)
            asset.sha256 = source_hash
            asset.size_bytes = source_size
            db.commit()
        except Exception:
            db.rollback()
            # compensate the half-written state: row still external, staged file must go
            try:
                destination.unlink()
                objects_dir.rmdir()
            except OSError:
                pass
            raise
        db.refresh(asset)
        return asset
    except ApiError:
        raise
    except OSError as error:
        db.rollback()
        raise ApiError("convert_failed", f"转托管失败：{error}", 400) from error
