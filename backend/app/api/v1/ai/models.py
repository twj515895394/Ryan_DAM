from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from backend.app.api.v1.deps import get_db
from backend.app.schemas.ai.model_config import (
    DefaultBindingPayload,
    DefaultBindingResponse,
    ModelProfileCreate,
    ModelProfileResponse,
    ModelProfileUpdate,
)
from backend.app.services.ai import model_service

router = APIRouter(prefix="/ai", tags=["ai_models"])


# --- Model Profiles ---


@router.get("/providers/{provider_id}/models", response_model=list[ModelProfileResponse])
def list_provider_models(provider_id: int, db: Session = Depends(get_db)) -> list[ModelProfileResponse]:
    return model_service.list_model_profiles(db, provider_id=provider_id)


@router.get("/models", response_model=list[ModelProfileResponse])
def list_all_models(db: Session = Depends(get_db)) -> list[ModelProfileResponse]:
    return model_service.list_model_profiles(db)


@router.post(
    "/providers/{provider_id}/models",
    response_model=ModelProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_model_profile(
    provider_id: int, payload: ModelProfileCreate, db: Session = Depends(get_db)
) -> ModelProfileResponse:
    return model_service.create_model_profile(db, provider_id, payload)


@router.get("/models/{model_id}", response_model=ModelProfileResponse)
def get_model_profile(model_id: int, db: Session = Depends(get_db)) -> ModelProfileResponse:
    return model_service.get_model_profile(db, model_id)


@router.patch("/models/{model_id}", response_model=ModelProfileResponse)
def update_model_profile(
    model_id: int, payload: ModelProfileUpdate, db: Session = Depends(get_db)
) -> ModelProfileResponse:
    return model_service.update_model_profile(db, model_id, payload)


@router.delete("/models/{model_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_model_profile(model_id: int, db: Session = Depends(get_db)) -> None:
    model_service.delete_model_profile(db, model_id)


# --- Default Bindings ---


@router.get("/defaults", response_model=list[DefaultBindingResponse])
def list_default_bindings(db: Session = Depends(get_db)) -> list[DefaultBindingResponse]:
    return model_service.list_default_bindings(db)


@router.post("/defaults", response_model=DefaultBindingResponse)
def set_default_binding(payload: DefaultBindingPayload, db: Session = Depends(get_db)) -> DefaultBindingResponse:
    return model_service.set_default_binding(db, payload)
