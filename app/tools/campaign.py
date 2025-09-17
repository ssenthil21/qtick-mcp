
from fastapi import APIRouter, Depends, HTTPException

from app.dependencies.services import get_campaign_service
from app.schemas.campaign import CampaignRequest, CampaignResponse
from app.services import CampaignService
from app.services.exceptions import ServiceError

router = APIRouter()

@router.post("/sendWhatsApp", response_model=CampaignResponse)
async def send_whatsapp(
    req: CampaignRequest,
    service: CampaignService = Depends(get_campaign_service),
):
    try:
        return await service.send_whatsapp(req)
    except ServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
