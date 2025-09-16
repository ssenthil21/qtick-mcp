
from fastapi import APIRouter
from app.schemas.appointment import (
    AppointmentRequest, AppointmentResponse,
    AppointmentListRequest, AppointmentListResponse, AppointmentSummary
)

router = APIRouter()

@router.post("/book", response_model=AppointmentResponse)
def book_appointment(req: AppointmentRequest):
    # Mock booking
    return AppointmentResponse(
        status="confirmed",
        appointment_id="APT-33451",
        queue_number="B17"
    )

@router.post("/list", response_model=AppointmentListResponse)
def list_appointments(req: AppointmentListRequest):
    # Mock dataset
    items = [
        AppointmentSummary(
            appointment_id="APT-33451",
            customer_name="Alex",
            service_id="haircut",
            datetime="2025-09-06T17:00:00+08:00",
            status="confirmed",
            queue_number="B17"
        ),
        AppointmentSummary(
            appointment_id="APT-33452",
            customer_name="Jane",
            service_id="facial",
            datetime="2025-09-06T18:30:00+08:00",
            status="pending",
            queue_number=None
        ),
    ]
    start = (req.page - 1) * req.page_size
    end = start + req.page_size
    return AppointmentListResponse(total=len(items), page=req.page, page_size=req.page_size, items=items[start:end])
