"""Bulk asset operations. Every operation returns per-item results so one
bad asset never masks the rest."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.errors import ApiError
from backend.app.models.asset import Asset
from backend.app.models.folder import Folder
from backend.app.models.tag import AssetTag, Tag


@dataclass
class ItemResult:
    asset_id: int
    ok: bool
    error: str | None = None


def _load_assets(db: Session, asset_ids: list[int]) -> dict[int, Asset]:
    unique = list(dict.fromkeys(asset_ids))
    if not unique:
        raise ApiError("validation_error", "资产列表不能为空。", 422)
    if len(unique) > 200:
        raise ApiError("validation_error", "单次批量操作最多支持 200 个资产。", 422)
    assets = db.scalars(select(Asset).where(Asset.id.in_(unique), Asset.status == "active")).all()
    found = {asset.id: asset for asset in assets}
    missing = [asset_id for asset_id in unique if asset_id not in found]
    if missing:
        raise ApiError("not_found", f"部分资产不存在或已被删除：{missing[:5]}", 404)
    return found


def _validate_external(asset: Asset, action: str) -> str | None:
    if asset.source_type == "external":
        return f"外部资产不支持{action}"
    return None


def bulk_add_tags(db: Session, asset_ids: list[int], tag_ids: list[int]) -> list[ItemResult]:
    if not tag_ids:
        raise ApiError("validation_error", "标签列表不能为空。", 422)
    assets = _load_assets(db, asset_ids)
    tags = db.scalars(select(Tag).where(Tag.id.in_(set(tag_ids)))).all()
    found_tags = {tag.id for tag in tags}
    missing = [tag_id for tag_id in set(tag_ids) if tag_id not in found_tags]
    if missing:
        raise ApiError("not_found", f"部分标签不存在：{missing[:5]}", 404)

    results: list[ItemResult] = []
    for asset_id, asset in assets.items():
        if error := _validate_external(asset, "打标签"):
            results.append(ItemResult(asset_id, False, error))
            continue
        for tag_id in found_tags:
            if db.get(AssetTag, (asset_id, tag_id)) is None:
                db.add(AssetTag(asset_id=asset_id, tag_id=tag_id))
        results.append(ItemResult(asset_id, True))
    db.commit()
    return results


def bulk_remove_tags(db: Session, asset_ids: list[int], tag_ids: list[int]) -> list[ItemResult]:
    if not tag_ids:
        raise ApiError("validation_error", "标签列表不能为空。", 422)
    assets = _load_assets(db, asset_ids)
    results: list[ItemResult] = []
    for asset_id, asset in assets.items():
        if error := _validate_external(asset, "移除标签"):
            results.append(ItemResult(asset_id, False, error))
            continue
        removed = 0
        for tag_id in set(tag_ids):
            link = db.get(AssetTag, (asset_id, tag_id))
            if link is not None:
                db.delete(link)
                removed += 1
        message = None if removed else "资产未打所选标签"
        results.append(ItemResult(asset_id, removed > 0, message))
    db.commit()
    return results


def bulk_move(db: Session, asset_ids: list[int], target_folder_id: int) -> list[ItemResult]:
    folder = db.get(Folder, target_folder_id)
    if folder is None:
        raise ApiError("not_found", "目标目录不存在或已被删除。", 404)
    assets = _load_assets(db, asset_ids)
    results: list[ItemResult] = []
    for asset_id, asset in assets.items():
        if error := _validate_external(asset, "移动"):
            results.append(ItemResult(asset_id, False, error))
            continue
        if asset.folder_id == target_folder_id:
            results.append(ItemResult(asset_id, False, "资产已在该目录"))
            continue
        asset.folder_id = target_folder_id
        results.append(ItemResult(asset_id, True))
    db.commit()
    return results
