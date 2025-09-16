
from pydantic import BaseModel
from typing import Optional

class LeadCreateRequest(BaseModel):
    business_id: str
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    source: Optional[str] = "manual"
    notes: Optional[str] = None

class LeadCreateResponse(BaseModel):
    lead_id: str
    status: str
    created_at: str
