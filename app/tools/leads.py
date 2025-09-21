
from fastapi import APIRouter, Depends, HTTPException

from app.dependencies.services import get_lead_service
from app.schemas.lead import (
    LeadCreateRequest,
    LeadCreateResponse,
    LeadListRequest,
    LeadListResponse,
)
from app.services import LeadService
from app.services.exceptions import ServiceError

router = APIRouter()

@router.post("/create", response_model=LeadCreateResponse)
async def create_lead(
    req: LeadCreateRequest,
    service: LeadService = Depends(get_lead_service),
):
    try:
        return await service.create(req)
    except ServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/list", response_model=LeadListResponse)
async def list_leads(
    req: LeadListRequest,
    service: LeadService = Depends(get_lead_service),
):
    try:
        return await service.list(req)
    except ServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
