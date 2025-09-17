
from fastapi import APIRouter, Depends, HTTPException

from app.dependencies.services import get_analytics_service
from app.schemas.analytics import AnalyticsRequest, AnalyticsResponse
from app.services import AnalyticsService
from app.services.exceptions import ServiceError

router = APIRouter()

@router.post("/report", response_model=AnalyticsResponse)
async def get_analytics(
    req: AnalyticsRequest,
    service: AnalyticsService = Depends(get_analytics_service),
):
    try:
        return await service.generate_report(req)
    except ServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
