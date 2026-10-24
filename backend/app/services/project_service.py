from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.core.errors import ApiError
from backend.app.models.folder import Folder
from backend.app.models.project import Project

MAX_PROJECT_NAME = 128


def _clean_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned:
        raise ApiError("validation_error", "项目名称不能为空。", 422)
    if len(cleaned) > MAX_PROJECT_NAME:
        raise ApiError("validation_error", f"项目名称不能超过 {MAX_PROJECT_NAME} 个字符。", 422)
    return cleaned


def _ensure_name_available(db: Session, name: str, *, exclude_id: int | None = None) -> None:
    stmt = select(Project).where(func.lower(Project.name) == name.lower())
    if exclude_id is not None:
        stmt = stmt.where(Project.id != exclude_id)
    if db.scalar(stmt) is not None:
        raise ApiError("duplicate_name", f"项目名称「{name}」已存在。", 409)


def get_project_or_404(db: Session, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise ApiError("not_found", "项目不存在或已被删除。", 404)
    return project


def list_projects(db: Session) -> list[Project]:
    return list(db.scalars(select(Project).order_by(Project.id)).all())


def create_project(db: Session, name: str) -> Project:
    cleaned = _clean_name(name)
    _ensure_name_available(db, cleaned)
    project = Project(name=cleaned)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def rename_project(db: Session, project_id: int, name: str) -> Project:
    project = get_project_or_404(db, project_id)
    cleaned = _clean_name(name)
    if cleaned != project.name:
        _ensure_name_available(db, cleaned, exclude_id=project.id)
    project.name = cleaned
    db.commit()
    db.refresh(project)
    return project


def delete_project(db: Session, project_id: int) -> None:
    project = get_project_or_404(db, project_id)
    folder_count = db.scalar(select(func.count(Folder.id)).where(Folder.project_id == project_id)) or 0
    if folder_count:
        raise ApiError("project_not_empty", f"项目仍包含 {folder_count} 个文件夹，请先处理这些目录后再删除项目。", 409)
    db.delete(project)
    db.commit()
