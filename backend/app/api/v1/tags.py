from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from backend.app.api.v1.deps import get_db
from backend.app.schemas.tag import AssetTagsUpdate, TagCreate, TagOut, TagUpdate, TagWithCount
from backend.app.services import tag_service

router = APIRouter(tags=["tags"])


def _tag_with_count(tag, count: int) -> TagWithCount:
    return TagWithCount(
        id=tag.id,
        name=tag.name,
        color=tag.color,
        created_at=tag.created_at,
        updated_at=tag.updated_at,
        asset_count=count,
    )


@router.get("/tags", response_model=list[TagWithCount])
def list_tags(db: Session = Depends(get_db)) -> list[TagWithCount]:
    return [_tag_with_count(tag, count) for tag, count in tag_service.list_tags(db)]


@router.post("/tags", response_model=TagWithCount, status_code=status.HTTP_201_CREATED)
def create_tag(payload: TagCreate, db: Session = Depends(get_db)) -> TagWithCount:
    tag = tag_service.create_tag(db, payload.name, payload.color)
    return _tag_with_count(tag, 0)


@router.patch("/tags/{tag_id}", response_model=TagWithCount)
def update_tag(tag_id: int, payload: TagUpdate, db: Session = Depends(get_db)) -> TagWithCount:
    tag = tag_service.rename_tag(db, tag_id, payload.name or "", payload.color)
    return _tag_with_count(tag, 0)


@router.delete("/tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_tag(tag_id: int, db: Session = Depends(get_db)) -> None:
    tag_service.delete_tag(db, tag_id)


@router.put("/assets/{asset_id}/tags", response_model=list[TagOut])
def set_asset_tags(asset_id: int, payload: AssetTagsUpdate, db: Session = Depends(get_db)) -> list[TagOut]:
    tags = tag_service.set_asset_tags(db, asset_id, payload.tag_ids)
    return [TagOut.model_validate(tag) for tag in tags]
