from fastapi import APIRouter, Depends, HTTPException

from app.dependencies.services import get_live_ops_service
from app.schemas.live_ops import LiveOpsRequest, LiveOpsResponse
from app.services.exceptions import ServiceError
from app.services.live_ops import LiveOperationsService

router = APIRouter()


@router.post("/events", response_model=LiveOpsResponse)
async def live_events(
    req: LiveOpsRequest,
    service: LiveOperationsService = Depends(get_live_ops_service),
):
    try:
        return await service.events(req)
    except ServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
