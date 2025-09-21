from fastapi import APIRouter, Depends, HTTPException

from app.dependencies.services import get_business_directory_service
from app.schemas.business import (
    BusinessSearchRequest,
    BusinessSearchResponse,
    ServiceLookupRequest,
    ServiceLookupResponse,
)
from app.services.business import BusinessDirectoryService
from app.services.exceptions import ServiceError

router = APIRouter()


@router.post("/search", response_model=BusinessSearchResponse)
async def search_businesses(
    req: BusinessSearchRequest,
    service: BusinessDirectoryService = Depends(get_business_directory_service),
):
    try:
        return await service.search(req)
    except ServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/services/find", response_model=ServiceLookupResponse)
async def find_service(
    req: ServiceLookupRequest,
    service: BusinessDirectoryService = Depends(get_business_directory_service),
):
    try:
        return await service.lookup_service(req)
    except ServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
