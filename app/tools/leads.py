
from fastapi import APIRouter
from app.schemas.lead import LeadCreateRequest, LeadCreateResponse
from datetime import datetime

router = APIRouter()

@router.post("/create", response_model=LeadCreateResponse)
def create_lead(req: LeadCreateRequest):
    # mock
    return LeadCreateResponse(
        lead_id="LEAD-90001",
        status="new",
        created_at=datetime.now().isoformat()
    )
