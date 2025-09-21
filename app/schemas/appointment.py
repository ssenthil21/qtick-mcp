
from pydantic import BaseModel
from typing import List, Optional

class AppointmentRequest(BaseModel):
    business_id: str
    customer_name: str
    service_id: int
    datetime: str

class AppointmentResponse(BaseModel):
    status: str
    appointment_id: str
    queue_number: str

class AppointmentListRequest(BaseModel):
    business_id: str
    date_from: Optional[str] = None  # ISO date
    date_to: Optional[str] = None    # ISO date
    status: Optional[str] = None     # confirmed | pending | cancelled
    page: int = 1
    page_size: int = 20

class AppointmentSummary(BaseModel):
    appointment_id: str
    customer_name: str
    service_id: int
    datetime: str
    status: str
    queue_number: Optional[str] = None

class AppointmentListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[AppointmentSummary]
