"""Trash pipeline for managed assets + index-only removal for external ones.

Managed delete moves the file into `<managed_root>/.trash/<asset-id>/` and
marks the row trashed; restore moves it back under `objects/`. Permanent
delete removes the trash directory and the DB row. External assets are
index-only: removing them NEVER touches source files (business invariant).
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.errors import ApiError
from backend.app.models.asset import Asset
from backend.app.models.folder import Folder
from backend.app.models.tag import AssetTag
from backend.app.models.import_job import ImportJobItem
from backend.app.services.fs_ops import replace_with_retry
from backend.app.services.settings_service import get_managed_root


@dataclass
class TrashItemResult:
    asset_id: int
    ok: bool
    error: str | None = None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _trash_dir_for(managed_root: str, asset_id: int) -> Path:
    return Path(managed_root) / ".trash" / str(asset_id)


def _objects_dir_for(managed_root: str, asset_id: int) -> Path:
    return Path(managed_root) / "objects" / str(asset_id)


def get_asset_or_404(db: Session, asset_id: int) -> Asset:
    asset = db.get(Asset, asset_id)
    if asset is None or asset.status != "active":
        raise ApiError("not_found", "资产不存在或已被删除。", 404)
    return asset


def delete_asset_index(db: Session, asset: Asset) -> None:
    """Remove an asset row and its associations (tags, import-job references).

    Shared by trash (external index-only removal) and external-source unlink.
    """
    for link in db.scalars(select(AssetTag).where(AssetTag.asset_id == asset.id)).all():
        db.delete(link)
    for item in db.scalars(select(ImportJobItem).where(ImportJobItem.asset_id == asset.id)).all():
        item.asset_id = None
    db.delete(asset)


def _remove_dir_if_empty(path: Path) -> None:
    try:
        path.rmdir()
    except OSError:
        pass  # not empty or already gone — nothing to clean


def trash_asset(db: Session, asset_id: int) -> None:
    asset = get_asset_or_404(db, asset_id)
    if asset.source_type == "external":
        # external: index-only removal, the source file stays untouched
        delete_asset_index(db, asset)
        db.commit()
        return

    managed_root = get_managed_root(db)
    source = Path(asset.file_path)
    if not source.is_file():
        raise ApiError("content_unavailable", "托管文件缺失，无法移入回收站。", 404)
    trash_dir = _trash_dir_for(managed_root, asset.id)
    trash_dir.mkdir(parents=True, exist_ok=True)
    destination = trash_dir / source.name
    replace_with_retry(source, destination, error_code="trash_failed", error_prefix="移入回收站失败")
    _remove_dir_if_empty(source.parent)
    asset.status = "trashed"
    asset.deleted_at = _utcnow()
    asset.original_folder_id = asset.folder_id
    asset.file_path = str(destination)
    try:
        db.commit()
    except Exception:
        db.rollback()
        # best-effort compensation: put the file back so the active row stays truthful
        try:
            os.replace(destination, source)
        except OSError:
            pass
        raise


def restore_asset(db: Session, asset_id: int, target_folder_id: int | None = None) -> None:
    asset = db.get(Asset, asset_id)
    if asset is None or asset.status != "trashed":
        raise ApiError("not_found", "回收站中不存在该资产。", 404)
    managed_root = get_managed_root(db)
    source = Path(asset.file_path)
    if not source.is_file():
        raise ApiError("content_unavailable", "回收站文件缺失，无法恢复。", 404)
    objects_dir = _objects_dir_for(managed_root, asset.id)
    objects_dir.mkdir(parents=True, exist_ok=True)
    destination = objects_dir / source.name
    replace_with_retry(source, destination, error_code="restore_failed", error_prefix="恢复失败")
    _remove_dir_if_empty(source.parent)
    asset.file_path = str(destination)
    asset.status = "active"
    asset.deleted_at = None

    if target_folder_id is not None:
        target_folder = db.get(Folder, target_folder_id)
        if target_folder is None:
            raise ApiError("not_found", "指定的恢复目标目录不存在。", 404)
        asset.folder_id = target_folder.id
    elif asset.original_folder_id is not None and db.get(Folder, asset.original_folder_id) is not None:
        asset.folder_id = asset.original_folder_id
    else:
        fallback = db.scalar(select(Folder).where(Folder.scope_type == "general").order_by(Folder.id))
        if fallback is None:
            fallback = Folder(name="已恢复资产", scope_type="general", sort_order=1)
            db.add(fallback)
            db.flush()
        asset.folder_id = fallback.id
    try:
        db.commit()
    except Exception:
        db.rollback()
        # best-effort compensation: move the file back into the trash dir
        try:
            os.replace(destination, source)
        except OSError:
            pass
        raise


def permanent_delete(db: Session, asset_id: int) -> None:
    asset = db.get(Asset, asset_id)
    if asset is None or asset.status != "trashed":
        raise ApiError("not_found", "回收站中不存在该资产。", 404)
    managed_root = get_managed_root(db)
    trash_dir = _trash_dir_for(managed_root, asset.id)
    if trash_dir.exists():
        try:
            shutil.rmtree(trash_dir)
        except OSError as error:
            raise ApiError(
                "trash_delete_failed",
                f"文件被占用，无法永久删除：{error}。请关闭正在使用该文件的程序后重试。",
                409,
            ) from error
    if trash_dir.exists():
        raise ApiError("trash_delete_failed", "磁盘文件未能删除，已保留回收站记录。", 409)
    delete_asset_index(db, asset)
    db.commit()


def empty_trash(db: Session) -> tuple[int, int]:
    """Remove every trashed asset; locked/unavailable items are skipped and reported."""
    trashed = db.scalars(select(Asset).where(Asset.status == "trashed")).all()
    removed = 0
    failed = 0
    for asset in trashed:
        try:
            permanent_delete(db, asset.id)
            removed += 1
        except ApiError:
            failed += 1
        except Exception:
            db.rollback()  # keep the session usable for the remaining items
            failed += 1
    return removed, failed


def list_trash(db: Session) -> list[dict]:
    rows = (
        db.query(Asset, Folder.name)
        .outerjoin(Folder, Asset.original_folder_id == Folder.id)
        .filter(Asset.status == "trashed")
        .order_by(Asset.deleted_at.desc(), Asset.id.desc())
        .all()
    )
    return [
        {
            "id": asset.id,
            "name": asset.name,
            "asset_type": asset.asset_type,
            "size_bytes": asset.size_bytes,
            "source_type": asset.source_type,
            "deleted_at": asset.deleted_at,
            "original_folder": folder_name or "（目录已删除）",
            "extension": asset.extension,
            "mime_type": asset.mime_type,
            "media_width": asset.media_width,
            "media_height": asset.media_height,
            "media_duration_ms": asset.media_duration_ms,
            "thumbnail_status": asset.thumbnail_status,
            "created_at": asset.created_at,
            "updated_at": asset.updated_at,
        }
        for asset, folder_name in rows
    ]


def bulk_trash(db: Session, asset_ids: list[int]) -> list[TrashItemResult]:
    """Delete many assets; per-item results so one bad file never masks the rest.

    Managed assets go to the trash; external ones just leave the index.
    """
    unique = list(dict.fromkeys(asset_ids))
    if not unique:
        raise ApiError("validation_error", "资产列表不能为空。", 422)
    if len(unique) > 200:
        raise ApiError("validation_error", "单次批量操作最多支持 200 个资产。", 422)
    assets = db.scalars(select(Asset).where(Asset.id.in_(unique), Asset.status == "active")).all()
    found = {asset.id for asset in assets}
    missing = [asset_id for asset_id in unique if asset_id not in found]
    if missing:
        raise ApiError("not_found", f"部分资产不存在或已被删除：{missing[:5]}", 404)

    results: list[TrashItemResult] = []
    for asset_id in unique:
        try:
            trash_asset(db, asset_id)
            results.append(TrashItemResult(asset_id, True))
        except ApiError as error:
            db.rollback()
            results.append(TrashItemResult(asset_id, False, error.message))
        except Exception:
            db.rollback()  # unexpected failure must not poison the remaining items
            results.append(TrashItemResult(asset_id, False, "删除失败，请重试。"))
    return results
