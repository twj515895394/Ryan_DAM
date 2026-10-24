"""Global tag management and asset-tag associations."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.core.errors import ApiError
from backend.app.models.asset import Asset
from backend.app.models.import_job import ImportJobItem  # noqa: F401  (keep mapper config simple)
from backend.app.models.tag import AssetTag, Tag

MAX_TAG_NAME = 64


def _clean_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned:
        raise ApiError("validation_error", "标签名称不能为空。", 422)
    if len(cleaned) > MAX_TAG_NAME:
        raise ApiError("validation_error", f"标签名称不能超过 {MAX_TAG_NAME} 个字符。", 422)
    return cleaned


def _ensure_name_available(db: Session, name: str, *, exclude_id: int | None = None) -> None:
    stmt = select(Tag).where(func.lower(Tag.name) == name.lower())
    if exclude_id is not None:
        stmt = stmt.where(Tag.id != exclude_id)
    if db.scalar(stmt) is not None:
        raise ApiError("duplicate_name", f"标签「{name}」已存在。", 409)


def list_tags(db: Session) -> list[tuple[Tag, int]]:
    counts = dict(
        db.execute(select(AssetTag.tag_id, func.count(AssetTag.asset_id)).group_by(AssetTag.tag_id)).all()
    )
    tags = db.scalars(select(Tag).order_by(Tag.name)).all()
    return [(tag, counts.get(tag.id, 0)) for tag in tags]


def get_tag_or_404(db: Session, tag_id: int) -> Tag:
    tag = db.get(Tag, tag_id)
    if tag is None:
        raise ApiError("not_found", "标签不存在或已被删除。", 404)
    return tag


def create_tag(db: Session, name: str, color: str | None = None) -> Tag:
    cleaned = _clean_name(name)
    _ensure_name_available(db, cleaned)
    tag = Tag(name=cleaned, color=color)
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return tag


def rename_tag(db: Session, tag_id: int, name: str, color: str | None = None) -> Tag:
    tag = get_tag_or_404(db, tag_id)
    cleaned = _clean_name(name)
    if cleaned.lower() != tag.name.lower():
        _ensure_name_available(db, cleaned, exclude_id=tag.id)
    tag.name = cleaned
    if color is not None:
        tag.color = color or None
    db.commit()
    db.refresh(tag)
    return tag


def delete_tag(db: Session, tag_id: int) -> None:
    tag = get_tag_or_404(db, tag_id)
    count = db.scalar(select(func.count(AssetTag.asset_id)).where(AssetTag.tag_id == tag_id)) or 0
    if count:
        raise ApiError(
            "tag_in_use",
            f"标签「{tag.name}」仍被 {count} 个资产使用，请先在这些资产上移除该标签。",
            409,
        )
    db.delete(tag)
    db.commit()


def add_tags_to_asset(db: Session, asset_id: int, tag_ids: list[int]) -> list[Tag]:
    asset = db.get(Asset, asset_id)
    if asset is None or asset.status != "active":
        raise ApiError("not_found", "资产不存在或已被删除。", 404)
    tags: list[Tag] = []
    for tag_id in dict.fromkeys(tag_ids):
        tag = db.get(Tag, tag_id)
        if tag is None:
            raise ApiError("not_found", f"标签 {tag_id} 不存在。", 404)
        exists = db.get(AssetTag, (asset_id, tag_id))
        if exists is None:
            db.add(AssetTag(asset_id=asset_id, tag_id=tag_id))
        tags.append(tag)
    db.commit()
    return tags


def set_asset_tags(db: Session, asset_id: int, tag_ids: list[int]) -> list[Tag]:
    """Replace the asset's tag set; unknown ids fail without partial changes."""
    asset = db.get(Asset, asset_id)
    if asset is None or asset.status != "active":
        raise ApiError("not_found", "资产不存在或已被删除。", 404)
    tags: list[Tag] = []
    for tag_id in dict.fromkeys(tag_ids):
        tag = db.get(Tag, tag_id)
        if tag is None:
            raise ApiError("not_found", f"标签 {tag_id} 不存在。", 404)
        tags.append(tag)
    current = db.scalars(select(AssetTag).where(AssetTag.asset_id == asset_id)).all()
    current_ids = {link.tag_id for link in current}
    target_ids = {tag.id for tag in tags}
    for link in current:
        if link.tag_id not in target_ids:
            db.delete(link)
    for tag_id in target_ids - current_ids:
        db.add(AssetTag(asset_id=asset_id, tag_id=tag_id))
    db.commit()
    return tags


def remove_tag_from_asset(db: Session, asset_id: int, tag_id: int) -> None:
    link = db.get(AssetTag, (asset_id, tag_id))
    if link is None:
        raise ApiError("not_found", "该资产未打此标签。", 404)
    db.delete(link)
    db.commit()


def tags_for_assets(db: Session, asset_ids: list[int]) -> dict[int, list[Tag]]:
    if not asset_ids:
        return {}
    rows = db.execute(
        select(AssetTag.asset_id, Tag)
        .join(Tag, AssetTag.tag_id == Tag.id)
        .where(AssetTag.asset_id.in_(asset_ids))
        .order_by(Tag.name)
    ).all()
    result: dict[int, list[Tag]] = {}
    for asset_id, tag in rows:
        result.setdefault(asset_id, []).append(tag)
    return result
