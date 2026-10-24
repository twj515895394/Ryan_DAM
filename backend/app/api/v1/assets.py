from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.app.api.v1.deps import get_db
from backend.app.core.errors import ApiError
from backend.app.models.asset import Asset
from backend.app.schemas.asset import AssetOut, AssetPage, MoveAssetPayload, RenameAssetPayload, TagBrief
from backend.app.services import asset_edit_service, asset_query, tag_service, thumbnail_service

router = APIRouter(tags=["assets"])


def _asset_out_with_tags(db: Session, asset: Asset) -> AssetOut:
    out = AssetOut.model_validate(asset)
    tags = tag_service.tags_for_assets(db, [asset.id]).get(asset.id, [])
    out.tags = [TagBrief(id=tag.id, name=tag.name, color=tag.color) for tag in tags]
    return out


@router.get("/assets", response_model=AssetPage)
def list_assets(
    scope: Literal["general", "project"] | None = Query(default=None),
    project_id: int | None = Query(default=None),
    folder_id: int | None = Query(default=None),
    q: str | None = Query(default=None, max_length=128),
    asset_type: Literal["image", "video", "audio", "document", "other"] | None = Query(default=None),
    size_min: int | None = Query(default=None, ge=0),
    size_max: int | None = Query(default=None, ge=0),
    modified_after: str | None = Query(default=None),
    modified_before: str | None = Query(default=None),
    tag_id: int | None = Query(default=None),
    sort: Literal["created_at", "updated_at", "name", "size"] = Query(default="created_at"),
    order: Literal["asc", "desc"] = Query(default="desc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> AssetPage:
    args = asset_query.AssetQuery(
        scope=scope,
        project_id=project_id,
        folder_id=folder_id,
        q=q,
        asset_type=asset_type,
        size_min=size_min,
        size_max=size_max,
        modified_after=asset_query.parse_datetime(modified_after, "modified_after"),
        modified_before=asset_query.parse_datetime(modified_before, "modified_before"),
        tag_id=tag_id,
        sort=sort,
        order=order,
    )
    query = asset_query.build_query(db, args)
    total = query.count()
    items = (
        query.offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    page_out = AssetPage(
        total=total,
        page=page,
        page_size=page_size,
        items=[AssetOut.model_validate(item) for item in items],
    )
    tags_by_asset = tag_service.tags_for_assets(db, [item.id for item in items])
    for item in page_out.items:
        item.tags = [TagBrief(id=tag.id, name=tag.name, color=tag.color) for tag in tags_by_asset.get(item.id, [])]
    return page_out

@router.patch("/assets/{asset_id}", response_model=AssetOut)
def rename_asset(asset_id: int, payload: RenameAssetPayload, db: Session = Depends(get_db)) -> AssetOut:
    asset = asset_edit_service.rename_asset(db, asset_id, payload.name)
    return _asset_out_with_tags(db, asset)


@router.post("/assets/{asset_id}/move", response_model=AssetOut)
def move_asset(asset_id: int, payload: MoveAssetPayload, db: Session = Depends(get_db)) -> AssetOut:
    asset = asset_edit_service.move_asset(db, asset_id, payload.folder_id)
    return _asset_out_with_tags(db, asset)


@router.post("/assets/{asset_id}/convert-to-managed", response_model=AssetOut)
def convert_to_managed(asset_id: int, db: Session = Depends(get_db)) -> AssetOut:
    """External → managed: copy + verify + update THIS record in place."""
    from backend.app.services import external_service

    asset = external_service.convert_to_managed(db, asset_id)
    return _asset_out_with_tags(db, asset)


@router.get("/assets/{asset_id}/thumbnail")
def get_asset_thumbnail(asset_id: int, db: Session = Depends(get_db)) -> FileResponse:
    asset = db.get(Asset, asset_id)
    if asset is None or asset.status != "active":
        raise ApiError("not_found", "资产不存在或已被删除。", 404)
    thumb = thumbnail_service.get_thumbnail(db, asset)
    if thumb is None or not thumb.exists():
        raise ApiError("thumbnail_unavailable", "缩略图尚未生成、生成失败或该资产没有可用封面。", 404)
    return FileResponse(thumb, media_type="image/jpeg")


@router.get("/assets/{asset_id}/content")
def get_asset_content(asset_id: int, db: Session = Depends(get_db)) -> FileResponse:
    """Serve the original file of a registered asset (path comes from the DB only).

    Starlette's FileResponse honours Range requests (206) so players can seek.
    """
    import mimetypes
    from pathlib import Path as FsPath

    asset = db.get(Asset, asset_id)
    if asset is None:
        raise ApiError("not_found", "资产不存在或已被删除。", 404)
    if asset.status == "missing":
        raise ApiError("content_unavailable", "外部源文件缺失或不可访问，请重新扫描外部目录。", 404)
    if asset.status != "active":
        raise ApiError("not_found", "资产不存在或已被删除。", 404)
    path = FsPath(asset.file_path)
    if not path.is_file():
        raise ApiError("content_unavailable", "资产文件缺失或不可访问。", 404)
    media_type = asset.mime_type or mimetypes.guess_type(asset.name)[0] or "application/octet-stream"
    return FileResponse(path, media_type=media_type, filename=asset.name)


@router.post("/assets/{asset_id}/open", status_code=204, response_model=None)
def open_asset_externally(asset_id: int, db: Session = Depends(get_db)) -> None:
    """Open the asset with the OS default application (Windows: os.startfile)."""
    import os

    asset = db.get(Asset, asset_id)
    if asset is None:
        raise ApiError("not_found", "资产不存在或已被删除。", 404)
    if asset.status == "missing":
        raise ApiError("content_unavailable", "外部源文件缺失或不可访问，请重新扫描外部目录。", 404)
    if asset.status != "active":
        raise ApiError("not_found", "资产不存在或已被删除。", 404)
    path = asset.file_path
    if not os.path.isfile(path):
        raise ApiError("content_unavailable", "资产文件缺失或不可访问。", 404)
    if not hasattr(os, "startfile"):
        raise ApiError("unsupported_platform", "当前平台不支持调用系统默认应用。", 400)
    os.startfile(path)  # noqa: S606 - user-initiated open of their own asset
