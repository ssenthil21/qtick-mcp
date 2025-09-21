
from typing import List, Optional

from pydantic import BaseModel, Field

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
    next_action: str
    follow_up_required: bool = Field(default=True)


class LeadSummary(BaseModel):
    lead_id: str
    name: str
    status: str
    created_at: str
    phone: Optional[str] = None
    email: Optional[str] = None
    source: Optional[str] = None


class LeadListRequest(BaseModel):
    business_id: str


class LeadListResponse(BaseModel):
    total: int
    items: List[LeadSummary]
