"""Asset listing queries: scope/folder filters plus search, type/size/time
filters and sorting (ticket 12)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.errors import ApiError
from backend.app.models.asset import Asset
from backend.app.models.folder import Folder
from backend.app.models.tag import AssetTag

SORT_FIELDS = {
    "created_at": Asset.created_at,
    "updated_at": Asset.updated_at,
    "name": Asset.name,
    "size": Asset.size_bytes,
}


@dataclass
class AssetQuery:
    scope: str | None = None
    project_id: int | None = None
    folder_id: int | None = None
    q: str | None = None
    asset_type: str | None = None
    size_min: int | None = None
    size_max: int | None = None
    modified_after: datetime | None = None
    modified_before: datetime | None = None
    tag_id: int | None = None
    sort: str = "created_at"
    order: str = "desc"


def parse_datetime(value: str | None, field: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError as error:
        raise ApiError("validation_error", f"{field} 不是有效的日期时间。", 422) from error


def build_query(db: Session, args: AssetQuery):
    # 'missing' external assets stay visible so the UI can flag them explicitly
    query = (
        db.query(Asset)
        .join(Folder, Asset.folder_id == Folder.id)
        .filter(Asset.status.in_(("active", "missing")))
    )
    if args.folder_id is not None:
        query = query.filter(Asset.folder_id == args.folder_id)
    elif args.scope == "general":
        query = query.filter(Folder.scope_type == "general")
    elif args.scope == "project":
        if args.project_id is None:
            raise ApiError("validation_error", "按项目查询资产时必须提供 project_id。", 422)
        query = query.filter(Folder.scope_type == "project", Folder.project_id == args.project_id)

    keyword = args.q.strip() if args.q else ""
    if keyword:
        if args.folder_id is None and args.scope is not None:
            # keyword also matches the folder subtree the assets live in
            scope_folders = db.scalars(
                select(Folder).where(_scope_condition(args.scope, args.project_id))
            ).all()
            children: dict[int | None, list[Folder]] = {}
            for folder in scope_folders:
                children.setdefault(folder.parent_id, []).append(folder)
            matched_ids: set[int] = set()
            stack = [f for f in scope_folders if keyword.lower() in f.name.lower()]
            while stack:
                current = stack.pop()
                matched_ids.add(current.id)
                stack.extend(children.get(current.id, []))
            if matched_ids:
                query = query.filter(
                    Asset.name.ilike(f"%{keyword}%") | Asset.folder_id.in_(matched_ids)
                )
            else:
                query = query.filter(Asset.name.ilike(f"%{keyword}%"))
        else:
            query = query.filter(Asset.name.ilike(f"%{keyword}%"))

    if args.asset_type:
        query = query.filter(Asset.asset_type == args.asset_type)
    if args.size_min is not None:
        query = query.filter(Asset.size_bytes >= args.size_min)
    if args.size_max is not None:
        query = query.filter(Asset.size_bytes <= args.size_max)
    if args.modified_after is not None:
        query = query.filter(Asset.updated_at >= args.modified_after)
    if args.modified_before is not None:
        query = query.filter(Asset.updated_at <= args.modified_before)
    if args.tag_id is not None:
        query = query.join(AssetTag, AssetTag.asset_id == Asset.id).filter(AssetTag.tag_id == args.tag_id)

    column = SORT_FIELDS.get(args.sort, Asset.created_at)
    direction = args.order if args.order in ("asc", "desc") else "desc"
    query = query.order_by(column.desc() if direction == "desc" else column.asc(), Asset.id.desc())
    return query


def _scope_condition(scope: str, project_id: int | None):
    if scope == "general":
        return Folder.scope_type == "general"
    return (Folder.scope_type == "project") & (Folder.project_id == project_id)
