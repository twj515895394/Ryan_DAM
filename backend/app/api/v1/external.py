"""External source endpoints: link a read-only directory and rescan it."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.api.v1.deps import get_db
from backend.app.schemas.external import (
    ExternalSourceCreated,
    ExternalSourceCreate,
    ExternalSourceOut,
    ScanResult,
    UnlinkResult,
)
from backend.app.services import external_service

router = APIRouter(tags=["external"])


@router.get("/external-sources", response_model=list[ExternalSourceOut])
def list_external_sources(db: Session = Depends(get_db)) -> list[ExternalSourceOut]:
    return [ExternalSourceOut(**row) for row in external_service.list_external_sources(db)]


@router.post("/external-sources", response_model=ExternalSourceCreated, status_code=201)
def create_external_source(payload: ExternalSourceCreate, db: Session = Depends(get_db)) -> ExternalSourceCreated:
    source, stats = external_service.create_external_source(
        db,
        root_path=payload.root_path,
        target_folder_id=payload.target_folder_id,
        target_project_id=payload.target_project_id,
        create_mount_folder=payload.create_mount_folder,
        display_name=payload.display_name,
    )
    rows = external_service.list_external_sources(db)
    row = next(item for item in rows if item["id"] == source.id)
    return ExternalSourceCreated(
        source=ExternalSourceOut(**row),
        scan=ScanResult(**stats),
    )


@router.post("/external-sources/{source_id}/scan", response_model=ScanResult)
def scan_external_source(source_id: int, db: Session = Depends(get_db)) -> ScanResult:
    source = external_service.get_source_or_404(db, source_id)
    return ScanResult(**external_service.scan_external_source(db, source))


@router.delete("/external-sources/{source_id}", response_model=UnlinkResult)
def unlink_external_source(source_id: int, db: Session = Depends(get_db)) -> UnlinkResult:
    """Unlink: drop the still-external index rows, keep converted ones, never
    touch source files."""
    removed, mount_removed = external_service.unlink_external_source(db, source_id)
    return UnlinkResult(removed=removed, mount_folder_removed=mount_removed)
