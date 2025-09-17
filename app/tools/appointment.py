
from fastapi import APIRouter, Depends, HTTPException
from app.schemas.appointment import (
    AppointmentRequest,
    AppointmentResponse,
    AppointmentListRequest,
    AppointmentListResponse,
)

from app.dependencies.services import get_appointment_service
from app.services import AppointmentService
from app.services.exceptions import ServiceError

router = APIRouter()


@router.post("/book", response_model=AppointmentResponse)
async def book_appointment(
    req: AppointmentRequest,
    service: AppointmentService = Depends(get_appointment_service),
):
    try:
        return await service.book(req)
    except ServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/list", response_model=AppointmentListResponse)
async def list_appointments(
    req: AppointmentListRequest,
    service: AppointmentService = Depends(get_appointment_service),
):
    try:
        return await service.list(req)
    except ServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
