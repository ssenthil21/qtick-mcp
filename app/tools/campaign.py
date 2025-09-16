
from fastapi import APIRouter
from app.schemas.campaign import CampaignRequest, CampaignResponse

router = APIRouter()

@router.post("/sendWhatsApp", response_model=CampaignResponse)
def send_whatsapp(req: CampaignRequest):
    # mock
    return CampaignResponse(
        status="sent",
        delivery_time="2025-09-05T15:02:03+08:00"
    )
