from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.app.api.v1.deps import get_db
from backend.app.core.errors import ApiError
from backend.app.models.asset import Asset
from backend.app.models.folder import Folder
from backend.app.schemas.asset import AssetOut, AssetPage
from backend.app.services import thumbnail_service

router = APIRouter(tags=["assets"])


@router.get("/assets", response_model=AssetPage)
def list_assets(
    scope: Literal["general", "project"] | None = Query(default=None),
    project_id: int | None = Query(default=None),
    folder_id: int | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> AssetPage:
    query = (
        db.query(Asset)
        .join(Folder, Asset.folder_id == Folder.id)
        .filter(Asset.status == "active")
    )
    if folder_id is not None:
        query = query.filter(Asset.folder_id == folder_id)
    elif scope == "general":
        query = query.filter(Folder.scope_type == "general")
    elif scope == "project":
        if project_id is None:
            raise ApiError("validation_error", "按项目查询资产时必须提供 project_id。", 422)
        query = query.filter(Folder.scope_type == "project", Folder.project_id == project_id)

    total = query.count()
    items = (
        query.order_by(Asset.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return AssetPage(
        total=total,
        page=page,
        page_size=page_size,
        items=[AssetOut.model_validate(item) for item in items],
    )


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
    """Serve the original file of a registered asset (path comes from the DB only)."""
    import mimetypes
    from pathlib import Path as FsPath

    asset = db.get(Asset, asset_id)
    if asset is None or asset.status != "active":
        raise ApiError("not_found", "资产不存在或已被删除。", 404)
    path = FsPath(asset.file_path)
    if not path.is_file():
        raise ApiError("content_unavailable", "资产文件缺失或不可访问。", 404)
    media_type = asset.mime_type or mimetypes.guess_type(asset.name)[0] or "application/octet-stream"
    return FileResponse(path, media_type=media_type, filename=asset.name)
