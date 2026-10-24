from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.api.v1.deps import get_db
from backend.app.schemas.settings import SettingsOut, SettingsUpdate
from backend.app.services import settings_service

router = APIRouter(tags=["settings"])


def _settings_payload(db: Session) -> SettingsOut:
    root = settings_service.get_managed_root(db)
    return SettingsOut(managed_root=root, managed_root_state=settings_service.describe_root_state(root))  # type: ignore[arg-type]


@router.get("/settings", response_model=SettingsOut)
def get_settings(db: Session = Depends(get_db)) -> SettingsOut:
    return _settings_payload(db)


@router.patch("/settings", response_model=SettingsOut)
def update_settings(payload: SettingsUpdate, db: Session = Depends(get_db)) -> SettingsOut:
    settings_service.update_managed_root(db, payload.managed_root)
    return _settings_payload(db)
