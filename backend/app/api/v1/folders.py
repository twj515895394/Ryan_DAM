from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.app.api.v1.deps import get_db
from backend.app.schemas.folder import FolderCreate, FolderNode, FolderOut, FolderUpdate
from backend.app.services import folder_service

router = APIRouter(tags=["folders"])


@router.get("/folders/tree", response_model=list[FolderNode])
def folder_tree(
    scope: Literal["general", "project"] = Query(...),
    project_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[FolderNode]:
    return folder_service.build_tree(db, scope=scope, project_id=project_id)


@router.post("/folders", response_model=FolderOut, status_code=status.HTTP_201_CREATED)
def create_folder(payload: FolderCreate, db: Session = Depends(get_db)) -> FolderOut:
    folder = folder_service.create_folder(
        db,
        name=payload.name,
        scope=payload.scope,
        project_id=payload.project_id,
        parent_id=payload.parent_id,
    )
    return FolderOut.model_validate(folder)


@router.patch("/folders/{folder_id}", response_model=FolderOut)
def update_folder(folder_id: int, payload: FolderUpdate, db: Session = Depends(get_db)) -> FolderOut:
    changes = payload.model_dump(exclude_unset=True)
    folder = folder_service.get_folder_or_404(db, folder_id)
    if "name" in changes and changes["name"] is not None:
        folder = folder_service.rename_folder(db, folder_id, changes["name"])
    if "parent_id" in changes:
        folder = folder_service.move_folder(db, folder_id, changes["parent_id"])
    return FolderOut.model_validate(folder)


@router.delete("/folders/{folder_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_folder(folder_id: int, db: Session = Depends(get_db)) -> None:
    folder_service.delete_folder(db, folder_id)
