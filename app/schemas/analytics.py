
from pydantic import BaseModel
from typing import List

class AnalyticsRequest(BaseModel):
    business_id: int
    metrics: List[str]
    period: str

class AnalyticsResponse(BaseModel):
    footfall: int
    revenue: str
    report_generated_at: str
