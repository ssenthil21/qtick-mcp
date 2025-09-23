
from fastapi import APIRouter, Depends, HTTPException

from app.dependencies.services import get_invoice_service
from app.schemas.billing import (
    InvoiceListRequest,
    InvoiceListResponse,
    InvoicePaymentRequest,
    InvoiceRequest,
    InvoiceResponse,
)
from app.services import InvoiceService
from app.services.exceptions import ServiceError

router = APIRouter()

@router.post("/create", response_model=InvoiceResponse)
async def create_invoice(
    req: InvoiceRequest,
    service: InvoiceService = Depends(get_invoice_service),
):
    try:
        return await service.create(req)
    except ServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/list", response_model=InvoiceListResponse)
async def list_invoices(
    req: InvoiceListRequest,
    service: InvoiceService = Depends(get_invoice_service),
):
    try:
        return await service.list(req)
    except ServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/mark-paid", response_model=InvoiceResponse)
async def mark_invoice_paid(
    req: InvoicePaymentRequest,
    service: InvoiceService = Depends(get_invoice_service),
):
    try:
        return await service.mark_paid(req)
    except ServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
