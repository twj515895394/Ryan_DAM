from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.app.api.v1.deps import get_db
from backend.app.schemas.ai.provider import (
    ProviderCreatePayload,
    ProviderResponse,
    ProviderTestPayload,
    ProviderTestResponse,
    ProviderUpdatePayload,
)
from backend.app.services.ai import provider_service

router = APIRouter(prefix="/ai/providers", tags=["ai_providers"])


@router.get("", response_model=list[ProviderResponse])
def list_providers(
    enabled_only: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> list[ProviderResponse]:
    return provider_service.list_providers(db, enabled_only=enabled_only)


@router.post("", response_model=ProviderResponse, status_code=status.HTTP_201_CREATED)
def create_provider(
    payload: ProviderCreatePayload,
    db: Session = Depends(get_db),
) -> ProviderResponse:
    return provider_service.create_provider(db, payload)


@router.get("/{provider_id}", response_model=ProviderResponse)
def get_provider(
    provider_id: int,
    db: Session = Depends(get_db),
) -> ProviderResponse:
    return provider_service.get_provider(db, provider_id)


@router.patch("/{provider_id}", response_model=ProviderResponse)
def update_provider(
    provider_id: int,
    payload: ProviderUpdatePayload,
    db: Session = Depends(get_db),
) -> ProviderResponse:
    return provider_service.update_provider(db, provider_id, payload)


@router.delete("/{provider_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_provider(
    provider_id: int,
    db: Session = Depends(get_db),
) -> None:
    provider_service.delete_provider(db, provider_id)


@router.post("/{provider_id}/test", response_model=ProviderTestResponse)
def test_provider(
    provider_id: int,
    payload: ProviderTestPayload,
    db: Session = Depends(get_db),
) -> ProviderTestResponse:
    return provider_service.test_provider_connection(db, provider_id, payload)
