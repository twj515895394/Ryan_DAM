from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.core.errors import ApiError
from backend.app.models.asset import Asset
from backend.app.models.folder import Folder
from backend.app.models.import_job import ImportJob, ImportJobItem
from backend.app.models.project import Project
from backend.app.schemas.folder import FolderNode, FolderStats

MAX_FOLDER_NAME = 255
_INVALID_NAME_CHARS = set('<>:"/\\|?*')


def _clean_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned:
        raise ApiError("validation_error", "目录名称不能为空。", 422)
    if len(cleaned) > MAX_FOLDER_NAME:
        raise ApiError("validation_error", f"目录名称不能超过 {MAX_FOLDER_NAME} 个字符。", 422)
    if cleaned in {".", ".."} or any(ch in _INVALID_NAME_CHARS for ch in cleaned):
        raise ApiError("validation_error", "目录名称不能包含 <>:\"/\\|?* 等字符。", 422)
    return cleaned


def _scope_filter(scope: str, project_id: int | None):
    if scope == "general":
        if project_id is not None:
            raise ApiError("validation_error", "通用资产库目录不接受 project_id。", 422)
        return Folder.scope_type == "general"
    if project_id is None:
        raise ApiError("validation_error", "项目目录必须指定 project_id。", 422)
    return (Folder.scope_type == "project") & (Folder.project_id == project_id)


def _validate_parent(db: Session, *, scope: str, project_id: int | None, parent_id: int | None) -> Folder | None:
    if parent_id is None:
        return None
    parent = db.get(Folder, parent_id)
    if parent is None:
        raise ApiError("not_found", "目标父目录不存在或已被删除。", 404)
    if parent.scope_type != scope:
        raise ApiError("invalid_parent", "通用资产库与项目资产库的目录不能互相嵌套。", 400)
    if scope == "project" and parent.project_id != project_id:
        raise ApiError("invalid_parent", "目录不能跨项目归属。", 400)
    return parent


def _ensure_sibling_name_free(db: Session, name: str, *, scope: str, project_id: int | None, parent_id: int | None, exclude_id: int | None = None) -> None:
    stmt = select(Folder).where(
        Folder.name == name,
        Folder.scope_type == scope,
        Folder.parent_id == parent_id,
    )
    if scope == "project":
        stmt = stmt.where(Folder.project_id == project_id)
    else:
        stmt = stmt.where(Folder.project_id.is_(None))
    if exclude_id is not None:
        stmt = stmt.where(Folder.id != exclude_id)
    if db.scalar(stmt) is not None:
        parent_label = f"「{db.get(Folder, parent_id).name}」" if parent_id else "顶层"
        raise ApiError("duplicate_name", f"{parent_label}下已存在同名目录「{name}」。", 409)


def create_folder(db: Session, *, name: str, scope: str, project_id: int | None = None, parent_id: int | None = None) -> Folder:
    cleaned = _clean_name(name)
    if scope == "project":
        if project_id is None:
            raise ApiError("validation_error", "项目目录必须指定所属项目。", 422)
        if db.get(Project, project_id) is None:
            raise ApiError("not_found", "项目不存在或已被删除。", 404)
    else:
        project_id = None
    parent = _validate_parent(db, scope=scope, project_id=project_id, parent_id=parent_id)
    _ensure_sibling_name_free(db, cleaned, scope=scope, project_id=project_id, parent_id=parent_id)

    next_order = (
        db.scalar(select(func.max(Folder.sort_order)).where(Folder.parent_id == parent_id)) or 0
    ) + 1
    folder = Folder(
        name=cleaned,
        scope_type=scope,
        project_id=project_id,
        parent_id=parent_id,
        sort_order=next_order,
    )
    db.add(folder)
    db.commit()
    db.refresh(folder)
    return folder


def get_folder_or_404(db: Session, folder_id: int) -> Folder:
    folder = db.get(Folder, folder_id)
    if folder is None:
        raise ApiError("not_found", "目录不存在或已被删除。", 404)
    return folder


def build_tree(db: Session, *, scope: str, project_id: int | None = None) -> list[FolderNode]:
    rows = db.scalars(
        select(Folder)
        .where(_scope_filter(scope, project_id))
        .order_by(Folder.sort_order, Folder.id)
    ).all()
    nodes: dict[int, FolderNode] = {}
    roots: list[FolderNode] = []
    for row in rows:
        nodes[row.id] = FolderNode(
            id=row.id,
            name=row.name,
            scope_type=row.scope_type,
            project_id=row.project_id,
            parent_id=row.parent_id,
            sort_order=row.sort_order,
            children=[],
        )
    for row in rows:
        node = nodes[row.id]
        if row.parent_id is not None and row.parent_id in nodes:
            nodes[row.parent_id].children.append(node)
        else:
            roots.append(node)
    return roots


def rename_folder(db: Session, folder_id: int, name: str) -> Folder:
    folder = get_folder_or_404(db, folder_id)
    cleaned = _clean_name(name)
    if cleaned != folder.name:
        _ensure_sibling_name_free(
            db,
            cleaned,
            scope=folder.scope_type,
            project_id=folder.project_id,
            parent_id=folder.parent_id,
            exclude_id=folder.id,
        )
    folder.name = cleaned
    db.commit()
    db.refresh(folder)
    return folder


def move_folder(db: Session, folder_id: int, parent_id: int | None) -> Folder:
    folder = get_folder_or_404(db, folder_id)
    if parent_id == folder.id:
        raise ApiError("invalid_move", "不能把目录移动到它自身。", 400)
    parent = _validate_parent(db, scope=folder.scope_type, project_id=folder.project_id, parent_id=parent_id)

    cursor = parent
    while cursor is not None:
        if cursor.id == folder.id:
            raise ApiError("invalid_move", "不能把目录移动到它自己的子目录下。", 400)
        cursor = db.get(Folder, cursor.parent_id) if cursor.parent_id is not None else None

    _ensure_sibling_name_free(
        db,
        folder.name,
        scope=folder.scope_type,
        project_id=folder.project_id,
        parent_id=parent_id,
        exclude_id=folder.id,
    )
    folder.parent_id = parent_id
    db.commit()
    db.refresh(folder)
    return folder


def ensure_folder_path(db: Session, *, base: Folder, parts: list[str]) -> Folder:
    """Find-or-create nested child folders mirroring an imported source tree."""
    current = base
    for part in parts:
        child = db.scalar(
            select(Folder).where(
                Folder.parent_id == current.id,
                Folder.name == part,
                Folder.scope_type == current.scope_type,
            )
        )
        if child is None:
            next_order = (
                db.scalar(select(func.max(Folder.sort_order)).where(Folder.parent_id == current.id)) or 0
            ) + 1
            child = Folder(
                name=part,
                scope_type=current.scope_type,
                project_id=current.project_id,
                parent_id=current.id,
                sort_order=next_order,
            )
            db.add(child)
            db.flush()
        current = child
    return current


def get_folder_subtree_ids(db: Session, folder_id: int) -> list[int]:
    """Return [folder_id, ...all descendant folder ids] in topological order."""
    all_ids = [folder_id]
    current_parents = [folder_id]
    while current_parents:
        children = db.scalars(
            select(Folder.id).where(Folder.parent_id.in_(current_parents))
        ).all()
        if not children:
            break
        all_ids.extend(children)
        current_parents = list(children)
    return all_ids


def get_folder_stats(db: Session, folder_id: int) -> FolderStats:
    folder = get_folder_or_404(db, folder_id)
    subtree_ids = get_folder_subtree_ids(db, folder_id)
    subfolder_count = len(subtree_ids) - 1

    assets = db.scalars(select(Asset).where(Asset.folder_id.in_(subtree_ids))).all()
    asset_count = len(assets)
    managed_count = sum(1 for a in assets if a.source_type == "managed")
    external_count = sum(1 for a in assets if a.source_type == "external")

    return FolderStats(
        folder_id=folder.id,
        folder_name=folder.name,
        subfolder_count=subfolder_count,
        asset_count=asset_count,
        managed_asset_count=managed_count,
        external_asset_count=external_count,
    )


def delete_folder(db: Session, folder_id: int, cascade: bool = False) -> None:
    folder = get_folder_or_404(db, folder_id)
    if not cascade:
        child_count = db.scalar(select(func.count(Folder.id)).where(Folder.parent_id == folder_id)) or 0
        if child_count:
            raise ApiError("folder_not_empty", f"目录「{folder.name}」仍包含 {child_count} 个子目录，请先处理子目录。", 409)
        asset_count = db.scalar(select(func.count(Asset.id)).where(Asset.folder_id == folder_id)) or 0
        if asset_count:
            raise ApiError("folder_not_empty", f"目录「{folder.name}」仍包含 {asset_count} 个资产，删除目录前请先移走资产。", 409)

        # Clear references to this folder from trashed assets and import jobs
        for trashed in db.scalars(select(Asset).where(Asset.original_folder_id == folder_id)).all():
            trashed.original_folder_id = None
        for job in db.scalars(select(ImportJob).where(ImportJob.target_folder_id == folder_id)).all():
            job.target_folder_id = None
        for item in db.scalars(select(ImportJobItem).where(ImportJobItem.target_folder_id == folder_id)).all():
            item.target_folder_id = None

        db.delete(folder)
        db.commit()
        return

    # Cascade mode:
    cascade_delete_folder_ids(db, [folder_id])


def cascade_delete_folder_ids(db: Session, root_ids: list[int]) -> None:
    """级联删除若干文件夹子树：托管资产移入回收站、外部资产仅移除索引、
    解除外部来源关联并清理任务引用。目录级联删除与项目级联删除共用此算法。"""
    from backend.app.services.trash_service import delete_asset_index, trash_asset
    from backend.app.services.external_service import unlink_external_source
    from backend.app.models.external_source import ExternalSource

    subtree_ids: list[int] = []
    seen: set[int] = set()
    for root_id in root_ids:
        for fid in get_folder_subtree_ids(db, root_id):
            if fid not in seen:
                seen.add(fid)
                subtree_ids.append(fid)

    # 1. Unlink any ExternalSource whose target_folder_id is in subtree_ids
    ext_sources = db.scalars(select(ExternalSource).where(ExternalSource.target_folder_id.in_(subtree_ids))).all()
    for src in ext_sources:
        unlink_external_source(db, src.id)

    # 2. Process all assets in subtree_ids
    assets = db.scalars(select(Asset).where(Asset.folder_id.in_(subtree_ids))).all()
    for asset in assets:
        if asset.source_type == "external":
            delete_asset_index(db, asset)
        else:
            # Managed asset
            if asset.status == "active":
                trash_asset(db, asset.id)
            # Ensure folder_id and original_folder_id are detached from deleted folders
            asset.folder_id = None
            asset.original_folder_id = None

    # 3. Clear original_folder_id for any other trashed assets referencing subtree_ids
    other_trashed = db.scalars(select(Asset).where(Asset.original_folder_id.in_(subtree_ids))).all()
    for asset in other_trashed:
        asset.original_folder_id = None

    # 4. Clear ImportJob / ImportJobItem target_folder_id
    for job in db.scalars(select(ImportJob).where(ImportJob.target_folder_id.in_(subtree_ids))).all():
        job.target_folder_id = None
    for item in db.scalars(select(ImportJobItem).where(ImportJobItem.target_folder_id.in_(subtree_ids))).all():
        item.target_folder_id = None

    db.flush()

    # 5. Clear parent_id for child folders in subtree to break FK dependencies
    for fid in subtree_ids:
        f = db.get(Folder, fid)
        if f is not None:
            f.parent_id = None
    db.flush()

    # 6. Delete all folders in subtree_ids (deepest first)
    for fid in reversed(subtree_ids):
        f = db.get(Folder, fid)
        if f is not None:
            db.delete(f)

    db.commit()
