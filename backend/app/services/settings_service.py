"""Managed-root storage settings.

Changing the default root only affects future imports; existing assets keep
their own recorded file_path, so nothing here may rewrite asset rows.
"""

from __future__ import annotations

import os
from sqlalchemy.orm import Session

from backend.app.core.errors import ApiError
from backend.app.models.app_setting import AppSetting

MANAGED_ROOT_KEY = "managed_root"
DEFAULT_MANAGED_ROOT = "D:\\Ryan_DAM\\assets"


def seed_default_settings(db: Session) -> None:
    if db.get(AppSetting, MANAGED_ROOT_KEY) is None:
        db.add(AppSetting(key=MANAGED_ROOT_KEY, value=DEFAULT_MANAGED_ROOT))
        db.commit()


def get_managed_root(db: Session) -> str:
    row = db.get(AppSetting, MANAGED_ROOT_KEY)
    return row.value if row is not None else DEFAULT_MANAGED_ROOT


def describe_root_state(path: str) -> str:
    drive, _ = os.path.splitdrive(path)
    if drive and not os.path.exists(drive + os.sep):
        return "unavailable"
    if not os.path.exists(path):
        return "missing"
    return "ok"


def normalize_managed_root(value: str) -> str:
    cleaned = value.strip().strip('"').strip("'")
    if not cleaned:
        raise ApiError("validation_error", "存储路径不能为空。", 422)
    if not os.path.isabs(cleaned):
        raise ApiError("validation_error", "存储路径必须是绝对路径，例如 D:\\Ryan_DAM\\assets。", 422)
    return cleaned


def update_managed_root(db: Session, value: str) -> str:
    cleaned = normalize_managed_root(value)
    row = db.get(AppSetting, MANAGED_ROOT_KEY)
    if row is None:
        row = AppSetting(key=MANAGED_ROOT_KEY, value=cleaned)
        db.add(row)
    else:
        row.value = cleaned
    db.commit()
    return cleaned
