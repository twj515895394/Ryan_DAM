from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from backend.app.api.v1.deps import get_db
from backend.app.schemas.project import ProjectCreate, ProjectOut, ProjectStats, ProjectUpdate
from backend.app.services import project_service

router = APIRouter(tags=["projects"])


@router.get("/projects", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db)) -> list[ProjectOut]:
    return [ProjectOut.model_validate(p) for p in project_service.list_projects(db)]


@router.post("/projects", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)) -> ProjectOut:
    project = project_service.create_project(db, payload.name)
    return ProjectOut.model_validate(project)


@router.patch("/projects/{project_id}", response_model=ProjectOut)
def rename_project(project_id: int, payload: ProjectUpdate, db: Session = Depends(get_db)) -> ProjectOut:
    project = project_service.rename_project(db, project_id, payload.name)
    return ProjectOut.model_validate(project)


@router.get("/projects/{project_id}/stats", response_model=ProjectStats)
def get_project_stats(project_id: int, db: Session = Depends(get_db)) -> ProjectStats:
    return project_service.get_project_stats(db, project_id)


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_project(project_id: int, cascade: bool = False, db: Session = Depends(get_db)) -> None:
    """cascade=True：连同全部子文件夹与资产级联删除（托管→回收站、外部→仅移除索引）。"""
    project_service.delete_project(db, project_id, cascade=cascade)
