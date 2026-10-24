"""Trash pipeline for managed assets + index-only removal for external ones.

Managed delete moves the file into `<managed_root>/.trash/<asset-id>/` and
marks the row trashed; restore moves it back under `objects/`. Permanent
delete removes the trash directory and the DB row. External assets are
index-only: removing them NEVER touches source files (business invariant).
"""

from __future__ import annotations

import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.errors import ApiError
from backend.app.models.asset import Asset
from backend.app.models.folder import Folder
from backend.app.models.tag import AssetTag
from backend.app.models.import_job import ImportJobItem
from backend.app.services.settings_service import get_managed_root


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


def _delete_index_row(db: Session, asset: Asset) -> None:
    for link in db.scalars(select(AssetTag).where(AssetTag.asset_id == asset.id)).all():
        db.delete(link)
    for item in db.scalars(select(ImportJobItem).where(ImportJobItem.asset_id == asset.id)).all():
        item.asset_id = None
    db.delete(asset)


def trash_asset(db: Session, asset_id: int) -> None:
    asset = get_asset_or_404(db, asset_id)
    if asset.source_type == "external":
        # external: index-only removal, the source file stays untouched
        _delete_index_row(db, asset)
        db.commit()
        return

    managed_root = get_managed_root(db)
    source = Path(asset.file_path)
    if not source.is_file():
        raise ApiError("content_unavailable", "托管文件缺失，无法移入回收站。", 404)
    trash_dir = _trash_dir_for(managed_root, asset.id)
    trash_dir.mkdir(parents=True, exist_ok=True)
    destination = trash_dir / source.name
    try:
        os.replace(source, destination)
    except OSError as error:
        raise ApiError("trash_failed", f"移入回收站失败：{error}", 400) from error
    asset.status = "trashed"
    asset.deleted_at = _utcnow()
    asset.original_folder_id = asset.folder_id
    asset.file_path = str(destination)
    db.commit()


def restore_asset(db: Session, asset_id: int) -> None:
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
    try:
        os.replace(source, destination)
    except OSError as error:
        raise ApiError("restore_failed", f"恢复失败：{error}", 400) from error
    asset.file_path = str(destination)
    asset.status = "active"
    asset.deleted_at = None
    if asset.original_folder_id is not None:
        asset.folder_id = asset.original_folder_id
    db.commit()


def permanent_delete(db: Session, asset_id: int) -> None:
    asset = db.get(Asset, asset_id)
    if asset is None or asset.status != "trashed":
        raise ApiError("not_found", "回收站中不存在该资产。", 404)
    managed_root = get_managed_root(db)
    trash_dir = _trash_dir_for(managed_root, asset.id)
    if trash_dir.exists():
        shutil.rmtree(trash_dir, ignore_errors=True)
    _delete_index_row(db, asset)
    db.commit()


def empty_trash(db: Session) -> int:
    trashed = db.scalars(select(Asset).where(Asset.status == "trashed")).all()
    for asset in trashed:
        permanent_delete(db, asset.id)
    return len(trashed)


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
        }
        for asset, folder_name in rows
    ]
