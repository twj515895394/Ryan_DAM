from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.api.v1.deps import get_db
from backend.app.core.errors import ApiError
from backend.app.schemas.bulk import BulkConvertPayload, BulkMovePayload, BulkResult, BulkTagsPayload
from backend.app.services import bulk_service

router = APIRouter(tags=["bulk"])


def _to_result(results) -> BulkResult:
    items = [
        {"asset_id": item.asset_id, "ok": item.ok, "error": item.error}
        for item in results
    ]
    return BulkResult(
        ok_count=sum(1 for item in results if item.ok),
        failed_count=sum(1 for item in results if not item.ok),
        items=items,
    )


@router.post("/assets/bulk-tags", response_model=BulkResult)
def bulk_tags(payload: BulkTagsPayload, db: Session = Depends(get_db)) -> BulkResult:
    if payload.add_tag_ids and payload.remove_tag_ids:
        raise ApiError("validation_error", "一次只能批量添加或批量移除标签，请分开操作。", 422)
    if not payload.add_tag_ids and not payload.remove_tag_ids:
        raise ApiError("validation_error", "标签列表不能为空。", 422)
    if payload.add_tag_ids:
        return _to_result(bulk_service.bulk_add_tags(db, payload.asset_ids, payload.add_tag_ids))
    return _to_result(bulk_service.bulk_remove_tags(db, payload.asset_ids, payload.remove_tag_ids))


@router.post("/assets/bulk-move", response_model=BulkResult)
def bulk_move(payload: BulkMovePayload, db: Session = Depends(get_db)) -> BulkResult:
    return _to_result(bulk_service.bulk_move(db, payload.asset_ids, payload.target_folder_id))


@router.post("/assets/bulk-convert-to-managed", response_model=BulkResult)
def bulk_convert_to_managed(payload: BulkConvertPayload, db: Session = Depends(get_db)) -> BulkResult:
    return _to_result(bulk_service.bulk_convert_to_managed(db, payload.asset_ids))
