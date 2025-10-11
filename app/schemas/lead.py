
from typing import List, Optional

from pydantic import BaseModel, Field

class LeadCreateRequest(BaseModel):
    business_id: int
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    source: Optional[str] = "manual"
    notes: Optional[str] = None
    location: Optional[str] = None
    enquiry_for: Optional[str] = None
    details: Optional[str] = None
    interest: Optional[int] = None
    follow_up_date: Optional[str] = None
    enquired_on: Optional[str] = None
    enquiry_for_time: Optional[str] = None
    attention_staff_id: Optional[int] = None
    attention_channel: Optional[str] = None
    third_status: Optional[str] = None

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
    business_id: int


class LeadListResponse(BaseModel):
    total: int
    items: List[LeadSummary]
