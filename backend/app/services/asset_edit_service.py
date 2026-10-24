"""Rename and move for single managed assets.

External assets are read-only: their files live outside the managed root and
must never be touched (business invariant), so both operations refuse them.
Move only updates folder_id — the physical file never moves (the managed
layout objects/<asset-id>/ is independent of the logical folder tree).
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.core.errors import ApiError
from backend.app.models.asset import Asset
from backend.app.models.folder import Folder
from backend.app.services.fs_ops import replace_with_retry
from backend.app.services.trash_service import get_asset_or_404

INVALID_NAME_CHARS = set('<>:"/\\|?*')


def _require_managed(asset: Asset, action: str) -> None:
    if asset.source_type == "external":
        raise ApiError("external_readonly", f"外部资产只读，不支持{action}。", 400)


def _resolve_target_name(asset: Asset, requested: str) -> str:
    cleaned = requested.strip()
    if not cleaned:
        raise ApiError("validation_error", "资产名称不能为空。", 422)
    if len(cleaned) > 255:
        raise ApiError("validation_error", "资产名称不能超过 255 个字符。", 422)
    if cleaned in {".", ".."} or any(ch in INVALID_NAME_CHARS for ch in cleaned):
        raise ApiError("validation_error", '资产名称不能包含 <>:"/\\|?* 等字符。', 422)

    original_suffix = Path(asset.name).suffix
    requested_suffix = Path(cleaned).suffix
    if requested_suffix:
        if original_suffix and requested_suffix.lower() != original_suffix.lower():
            raise ApiError(
                "validation_error",
                f"重命名不支持修改扩展名，请保持 {original_suffix}（扩展名会自动保留）。",
                422,
            )
        return cleaned
    # default: keep the original extension
    return cleaned + original_suffix


def rename_asset(db: Session, asset_id: int, requested: str) -> Asset:
    asset = get_asset_or_404(db, asset_id)
    _require_managed(asset, "重命名")
    final_name = _resolve_target_name(asset, requested)

    if final_name != asset.name:
        conflict = db.scalar(
            select(func.count(Asset.id)).where(
                Asset.folder_id == asset.folder_id,
                Asset.id != asset.id,
                Asset.status == "active",
                func.lower(Asset.name) == final_name.lower(),
            )
        ) or 0
        if conflict:
            raise ApiError("duplicate_name", "同目录下已存在同名资产。", 409)

        source = Path(asset.file_path)
        if not source.is_file():
            raise ApiError("content_unavailable", "托管文件缺失，无法重命名。", 404)
        destination = source.parent / final_name
        if destination.exists() and destination != source:
            raise ApiError("duplicate_name", "目标文件名已存在于托管目录。", 409)
        replace_with_retry(source, destination, error_code="rename_failed", error_prefix="重命名失败")
        asset.name = final_name
        asset.extension = Path(final_name).suffix.lstrip(".") or None
        asset.file_path = str(destination)
        db.commit()
        db.refresh(asset)
    return asset


def move_asset(db: Session, asset_id: int, target_folder_id: int) -> Asset:
    asset = get_asset_or_404(db, asset_id)
    _require_managed(asset, "移动")
    folder = db.get(Folder, target_folder_id)
    if folder is None:
        raise ApiError("not_found", "目标目录不存在或已被删除。", 404)
    if asset.folder_id == target_folder_id:
        raise ApiError("already_in_folder", "资产已在该目录。", 400)

    current = db.get(Folder, asset.folder_id)
    if current is not None:
        if current.scope_type != folder.scope_type:
            raise ApiError("invalid_move", "通用资产库与项目资产库之间不能移动资产。", 400)
        if current.scope_type == "project" and current.project_id != folder.project_id:
            raise ApiError("invalid_move", "不能跨项目移动资产。", 400)

    asset.folder_id = target_folder_id
    db.commit()
    db.refresh(asset)
    return asset
