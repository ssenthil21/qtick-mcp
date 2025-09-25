
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

class AnalyticsRequest(BaseModel):
    business_id: int
    metrics: List[str]
    period: str

class ServiceBookingSummary(BaseModel):
    service_id: Optional[int] = None
    name: str
    booking_count: int


class ServiceRevenueSummary(BaseModel):
    service_id: Optional[int] = None
    name: str
    total_revenue: float
    currency: Optional[str] = None


class StatusBreakdown(BaseModel):
    total: int
    by_status: Dict[str, int] = Field(default_factory=dict)


class AppointmentAnalytics(StatusBreakdown):
    unique_customers: int = 0


class InvoiceAnalytics(StatusBreakdown):
    total_revenue: float
    paid_total: float
    outstanding_total: float
    average_invoice_value: Optional[float] = None
    currency: Optional[str] = None
    unique_customers: int = 0


class LeadAnalytics(StatusBreakdown):
    source_breakdown: Dict[str, int] = Field(default_factory=dict)


class AnalyticsResponse(BaseModel):
    footfall: int
    revenue: str
    report_generated_at: str
    top_appointment_service: Optional[ServiceBookingSummary] = None
    highest_revenue_service: Optional[ServiceRevenueSummary] = None
    appointment_summary: Optional[AppointmentAnalytics] = None
    invoice_summary: Optional[InvoiceAnalytics] = None
    lead_summary: Optional[LeadAnalytics] = None
