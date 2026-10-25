"""Trash endpoints: managed delete/restore/permanent-delete/empty.

Business invariants: managed deletion goes to the trash (recoverable until a
permanent delete), external deletion only removes the index row and NEVER
touches source files on disk.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.api.v1.deps import get_db
from backend.app.schemas.bulk import BulkItemResult, BulkResult, BulkTrashPayload
from backend.app.schemas.trash import TrashEmptyResult, TrashItem, TrashList
from backend.app.services import trash_service

router = APIRouter(tags=["trash"])


@router.delete("/assets/{asset_id}", status_code=204, response_model=None)
def delete_asset(asset_id: int, db: Session = Depends(get_db)) -> None:
    """Delete one asset: managed → trash, external → index-only removal."""
    trash_service.trash_asset(db, asset_id)


@router.get("/trash", response_model=TrashList)
def list_trash(db: Session = Depends(get_db)) -> TrashList:
    items = trash_service.list_trash(db)
    return TrashList(total=len(items), items=[TrashItem(**item) for item in items])


@router.post("/trash/{asset_id}/restore", status_code=204, response_model=None)
def restore_trashed(
    asset_id: int,
    target_folder_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
) -> None:
    trash_service.restore_asset(db, asset_id, target_folder_id=target_folder_id)


@router.delete("/trash/{asset_id}", status_code=204, response_model=None)
def permanent_delete_trashed(asset_id: int, db: Session = Depends(get_db)) -> None:
    trash_service.permanent_delete(db, asset_id)


@router.post("/trash/empty", response_model=TrashEmptyResult)
def empty_trash(db: Session = Depends(get_db)) -> TrashEmptyResult:
    removed, failed = trash_service.empty_trash(db)
    return TrashEmptyResult(removed=removed, failed=failed)


@router.post("/assets/bulk-trash", response_model=BulkResult)
def bulk_trash(payload: BulkTrashPayload, db: Session = Depends(get_db)) -> BulkResult:
    results = trash_service.bulk_trash(db, payload.asset_ids)
    return BulkResult(
        ok_count=sum(1 for item in results if item.ok),
        failed_count=sum(1 for item in results if not item.ok),
        items=[
            BulkItemResult(asset_id=item.asset_id, ok=item.ok, error=item.error)
            for item in results
        ],
    )
