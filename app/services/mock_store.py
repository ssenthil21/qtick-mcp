from __future__ import annotations

import itertools
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import DefaultDict, Dict, List, Optional

from app.schemas.analytics import AnalyticsRequest, AnalyticsResponse
from app.schemas.appointment import (
    AppointmentListRequest,
    AppointmentListResponse,
    AppointmentRequest,
    AppointmentResponse,
    AppointmentSummary,
)
from app.schemas.billing import InvoiceRequest, InvoiceResponse
from app.schemas.campaign import CampaignRequest, CampaignResponse
from app.schemas.lead import LeadCreateRequest, LeadCreateResponse


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class _BaseRepository:
    def __init__(self, prefix: str) -> None:
        self._prefix = prefix
        self._counter = itertools.count(1)

    def _next_id(self) -> str:
        return f"{self._prefix}-{next(self._counter):05d}"


class AppointmentRepository(_BaseRepository):
    def __init__(self) -> None:
        super().__init__("APT")
        self._appointments: Dict[str, Dict[str, str]] = {}
        self._queue_numbers: DefaultDict[str, itertools.count] = defaultdict(
            lambda: itertools.count(1)
        )

    async def book(self, request: AppointmentRequest) -> AppointmentResponse:
        appointment_id = self._next_id()
        queue_number = f"B{next(self._queue_numbers[request.business_id]):02d}"
        record = {
            "appointment_id": appointment_id,
            "business_id": request.business_id,
            "customer_name": request.customer_name,
            "service_id": request.service_id,
            "datetime": request.datetime,
            "status": "confirmed",
            "queue_number": queue_number,
        }
        self._appointments[appointment_id] = record
        return AppointmentResponse(
            status="confirmed",
            appointment_id=appointment_id,
            queue_number=queue_number,
        )

    async def list(self, request: AppointmentListRequest) -> AppointmentListResponse:
        filtered = [
            AppointmentSummary(
                appointment_id=record["appointment_id"],
                customer_name=record["customer_name"],
                service_id=record["service_id"],
                datetime=record["datetime"],
                status=record["status"],
                queue_number=record["queue_number"],
            )
            for record in self._appointments.values()
            if record["business_id"] == request.business_id
        ]

        start = (request.page - 1) * request.page_size
        end = start + request.page_size
        page_items = filtered[start:end]

        return AppointmentListResponse(
            total=len(filtered),
            page=request.page,
            page_size=request.page_size,
            items=page_items,
        )

    async def get(self, appointment_id: str) -> Optional[Dict[str, str]]:
        appointment = self._appointments.get(appointment_id)
        return dict(appointment) if appointment is not None else None


class InvoiceRepository(_BaseRepository):
    def __init__(self) -> None:
        super().__init__("INV")
        self._invoices: Dict[str, Dict[str, object]] = {}

    async def create(self, request: InvoiceRequest) -> InvoiceResponse:
        total = 0.0
        for item in request.items:
            unit_price = getattr(item, "unit_price", None)
            if unit_price is None:
                unit_price = getattr(item, "price", None)
            if unit_price is None:
                unit_price = 0.0
            line_total = float(item.quantity) * float(unit_price)
            line_total *= 1.0 + float(item.tax_rate)
            total += line_total
        total = round(total, 2)

        invoice_id = self._next_id()
        record = {
            "invoice_id": invoice_id,
            "business_id": request.business_id,
            "total": total,
            "currency": request.currency,
            "created_at": _utc_now_iso(),
            "payment_link": f"https://pay.qtick.co/{invoice_id}",
            "status": "created",
        }
        self._invoices[invoice_id] = record
        return InvoiceResponse(**record)

    async def list(self, business_id: Optional[str] = None) -> List[Dict[str, object]]:
        if business_id is None:
            return [dict(invoice) for invoice in self._invoices.values()]
        return [
            dict(invoice)
            for invoice in self._invoices.values()
            if invoice["business_id"] == business_id
        ]

    async def get(self, invoice_id: str) -> Optional[Dict[str, object]]:
        invoice = self._invoices.get(invoice_id)
        return dict(invoice) if invoice is not None else None


class LeadRepository(_BaseRepository):
    def __init__(self) -> None:
        super().__init__("LEAD")
        self._leads: Dict[str, Dict[str, object]] = {}

    async def create(self, request: LeadCreateRequest) -> LeadCreateResponse:
        lead_id = self._next_id()
        record = {
            "lead_id": lead_id,
            "business_id": request.business_id,
            "status": "new",
            "created_at": _utc_now_iso(),
            "name": request.name,
            "phone": request.phone,
            "email": request.email,
            "source": request.source,
            "notes": request.notes,
        }
        self._leads[lead_id] = record
        return LeadCreateResponse(
            lead_id=lead_id,
            status="new",
            created_at=record["created_at"],
        )

    async def list(self, business_id: Optional[str] = None) -> List[Dict[str, object]]:
        if business_id is None:
            return [dict(lead) for lead in self._leads.values()]
        return [
            dict(lead)
            for lead in self._leads.values()
            if lead["business_id"] == business_id
        ]

    async def get(self, lead_id: str) -> Optional[Dict[str, object]]:
        lead = self._leads.get(lead_id)
        return dict(lead) if lead is not None else None


class CampaignRepository(_BaseRepository):
    def __init__(self) -> None:
        super().__init__("CMP")
        self._campaigns: Dict[str, Dict[str, object]] = {}

    async def send_whatsapp(self, request: CampaignRequest) -> CampaignResponse:
        campaign_id = self._next_id()
        delivery_time = _utc_now_iso()
        record = {
            "campaign_id": campaign_id,
            "customer_name": request.customer_name,
            "phone_number": request.phone_number,
            "message_template": request.message_template,
            "offer_code": request.offer_code,
            "expiry": request.expiry,
            "status": "sent",
            "delivery_time": delivery_time,
        }
        self._campaigns[campaign_id] = record
        return CampaignResponse(status="sent", delivery_time=delivery_time)

    async def list(self) -> List[Dict[str, object]]:
        return [dict(campaign) for campaign in self._campaigns.values()]

    async def get(self, campaign_id: str) -> Optional[Dict[str, object]]:
        campaign = self._campaigns.get(campaign_id)
        return dict(campaign) if campaign is not None else None


class AnalyticsRepository:
    def __init__(
        self,
        appointment_repository: AppointmentRepository,
        invoice_repository: InvoiceRepository,
    ) -> None:
        self._appointments = appointment_repository
        self._invoices = invoice_repository

    async def generate_report(self, request: AnalyticsRequest) -> AnalyticsResponse:
        appointments = await self._appointments.list(
            AppointmentListRequest(
                business_id=request.business_id,
                page=1,
                page_size=10_000,
            )
        )
        footfall = appointments.total

        invoices = await self._invoices.list(request.business_id)
        total_revenue = sum(float(invoice["total"]) for invoice in invoices)
        revenue_display = f"SGD {total_revenue:,.2f}"

        return AnalyticsResponse(
            footfall=footfall,
            revenue=revenue_display,
            report_generated_at=_utc_now_iso(),
        )


@dataclass
class MockDataStore:
    appointments: AppointmentRepository
    invoices: InvoiceRepository
    leads: LeadRepository
    campaigns: CampaignRepository
    analytics: AnalyticsRepository


_mock_store: Optional[MockDataStore] = None


def get_mock_store() -> MockDataStore:
    global _mock_store
    if _mock_store is None:
        appointments = AppointmentRepository()
        invoices = InvoiceRepository()
        leads = LeadRepository()
        campaigns = CampaignRepository()
        analytics = AnalyticsRepository(appointments, invoices)
        _mock_store = MockDataStore(
            appointments=appointments,
            invoices=invoices,
            leads=leads,
            campaigns=campaigns,
            analytics=analytics,
        )
    return _mock_store


def reset_mock_store() -> None:
    global _mock_store
    _mock_store = None
