from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from backend.app.api.v1.deps import get_db
from backend.app.core.errors import ApiError
from backend.app.models.import_job import ImportJob, ImportJobItem
from backend.app.schemas.import_job import FolderImportCreate, ImportCreate, ImportJobItemOut, ImportJobOut
from backend.app.services import import_service

router = APIRouter(tags=["imports"])


@router.post("/imports", response_model=ImportJobOut, status_code=status.HTTP_202_ACCEPTED)
def create_import(payload: ImportCreate, db: Session = Depends(get_db)) -> ImportJobOut:
    job = import_service.create_import(
        db, paths=payload.paths, folder_id=payload.folder_id, allow_duplicates=payload.allow_duplicates
    )
    return _job_out(db, job.id)


@router.post("/imports/folder", response_model=ImportJobOut, status_code=status.HTTP_202_ACCEPTED)
def create_folder_import(payload: FolderImportCreate, db: Session = Depends(get_db)) -> ImportJobOut:
    job = import_service.create_folder_import(
        db, source_dir=payload.source_dir, folder_id=payload.folder_id, allow_duplicates=payload.allow_duplicates
    )
    return _job_out(db, job.id)


@router.get("/imports/{job_id}", response_model=ImportJobOut)
def get_import(job_id: int, db: Session = Depends(get_db)) -> ImportJobOut:
    if db.get(ImportJob, job_id) is None:
        raise ApiError("not_found", "导入任务不存在。", 404)
    return _job_out(db, job_id)


def _job_out(db: Session, job_id: int) -> ImportJobOut:
    job = db.get(ImportJob, job_id)
    if job is None:
        raise ApiError("not_found", "导入任务不存在。", 404)
    items = (
        db.query(ImportJobItem)
        .filter(ImportJobItem.job_id == job_id)
        .order_by(ImportJobItem.id)
        .all()
    )
    out = ImportJobOut.model_validate(job)
    out.items = [ImportJobItemOut.model_validate(item) for item in items]
    return out
