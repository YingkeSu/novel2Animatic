"""Model services router (issue #3).

REST surface:
- POST   /api/services            register a preset or custom service
- GET    /api/services            list services (api_key masked)
- GET    /api/services/{id}       get one service (api_key masked)
- DELETE /api/services/{id}       remove a service
- POST   /api/services/{id}/probe probe connectivity + enumerate models

All routes require authentication. The decrypted API key is never present
in any response; only a masked representation is returned.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas import ServiceCreate, ServiceResponse, ServiceProbeResponse
from app.services.auth import get_current_user
from app.services import model_registry, probe

router = APIRouter(prefix="/api/services", tags=["services"])


@router.post("", response_model=ServiceResponse)
async def create_service(
    req: ServiceCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Register a model service — from a preset or as a custom endpoint."""
    if req.preset_id:
        preset = model_registry.get_preset_by_id(req.preset_id)
        if preset is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown preset")
        svc = await model_registry.create_service_from_preset(db, preset, api_key=req.api_key)
    else:
        # validators guarantee these are present when preset_id is absent
        svc = await model_registry.create_service(
            db,
            name=req.name,
            group=req.group,
            base_url=req.base_url,
            api_key=req.api_key,
            api_format=req.api_format,
            stream=req.stream,
            models=req.models,
            is_preset=False,
        )
    return model_registry.service_to_dict(svc)


@router.get("", response_model=list[ServiceResponse])
async def list_services(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await model_registry.list_services_as_dicts(db)


@router.get("/{service_id}", response_model=ServiceResponse)
async def get_service(
    service_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    svc = await model_registry.get_service(db, service_id)
    if svc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")
    return model_registry.service_to_dict(svc)


@router.delete("/{service_id}")
async def delete_service(
    service_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    deleted = await model_registry.delete_service(db, service_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")
    return {"detail": "deleted"}


@router.post("/{service_id}/probe", response_model=ServiceProbeResponse)
async def probe_service_endpoint(
    service_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Probe a registered service: enumerate models + detect stream support."""
    svc = await model_registry.get_service(db, service_id)
    if svc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")

    api_key = await model_registry.get_decrypted_api_key(svc)
    result = await probe.probe_service(
        base_url=svc.base_url,
        api_key=api_key,
        api_format=svc.api_format,
    )

    # Stamp probe time on success.
    if result.get("success"):
        # Column is TIMESTAMP WITHOUT TIME ZONE; store naive UTC to avoid
        # offset-aware/naive mismatch with asyncpg.
        svc.probed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await db.commit()

    return result
