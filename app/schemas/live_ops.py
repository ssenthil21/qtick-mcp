from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from app.schemas.business import BusinessSummary


LiveOpsEventType = Literal["appointment", "invoice", "lead", "review", "system"]


class LiveOpsRequest(BaseModel):
    business_id: int = Field(..., description="Target business identifier")
    date: Optional[str] = Field(
        None,
        description="ISO date (YYYY-MM-DD) to summarise. Defaults to today in UTC.",
    )


class LiveOpsEvent(BaseModel):
    event_type: LiveOpsEventType
    summary: str
    timestamp: str
    details: Dict[str, object] = Field(default_factory=dict)


class BusinessEventGroup(BaseModel):
    business: BusinessSummary
    services: List[Dict[str, object]]


class LiveOpsResponse(BaseModel):
    business: BusinessSummary
    date: str
    generated_at: str
    total_events: int
    events: List[LiveOpsEvent]
