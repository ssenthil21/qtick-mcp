from __future__ import annotations

import itertools
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import DefaultDict, Dict, Iterable, List, Optional

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
from app.schemas.business import BusinessSearchResponse, BusinessSummary, ServiceSummary
from app.schemas.lead import LeadCreateRequest, LeadCreateResponse


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class _BaseRepository:
    def __init__(self, prefix: str) -> None:
        self._prefix = prefix
        self._counter = itertools.count(1)

    def _next_id(self) -> str:
        return f"{self._prefix}-{next(self._counter):05d}"


class BusinessRecord:
    def __init__(
        self,
        *,
        business_id: int,
        slug: str,
        name: str,
        location: str,
        tags: Iterable[str],
        services: Iterable["ServiceRecord"],
    ) -> None:
        self.business_id = int(business_id)
        self.slug = slug.lower()
        self.name = name
        self.location = location
        self.tags = list(tags)
        self.services = list(services)


class ServiceRecord:
    def __init__(
        self,
        *,
        service_id: int,
        name: str,
        category: str,
        duration_minutes: int,
        price: float,
    ) -> None:
        self.service_id = int(service_id)
        self.name = name
        self.category = category
        self.duration_minutes = duration_minutes
        self.price = price


class MasterDataRepository:
    def __init__(self) -> None:
        self._businesses_by_id: Dict[int, BusinessRecord] = {}
        self._businesses_by_slug: Dict[str, BusinessRecord] = {}
        self._seed_businesses()

    def _seed_businesses(self) -> None:
        chillbreeze_services = [
            ServiceRecord(
                service_id=101,
                name="Signature Haircut",
                category="grooming",
                duration_minutes=45,
                price=38.0,
            ),
            ServiceRecord(
                service_id=102,
                name="Classic Facial",
                category="spa",
                duration_minutes=60,
                price=68.0,
            ),
            ServiceRecord(
                service_id=103,
                name="Aromatherapy Massage",
                category="spa",
                duration_minutes=75,
                price=96.0,
            ),
            ServiceRecord(
                service_id=104,
                name="Kids Haircut",
                category="grooming",
                duration_minutes=30,
                price=25.0,
            ),
        ]

        anna_nagar_services = [
            ServiceRecord(
                service_id=201,
                name="Chillrezze Blowout",
                category="styling",
                duration_minutes=50,
                price=54.0,
            ),
            ServiceRecord(
                service_id=202,
                name="Festive Mehndi",
                category="beauty",
                duration_minutes=90,
                price=72.0,
            ),
        ]

        adayar_services = [
            ServiceRecord(
                service_id=301,
                name="Beach Breeze Haircut",
                category="grooming",
                duration_minutes=40,
                price=36.0,
            ),
            ServiceRecord(
                service_id=302,
                name="Soothing Head Massage",
                category="spa",
                duration_minutes=45,
                price=42.0,
            ),
        ]

        self.add_business(
            BusinessRecord(
                business_id=1001,
                slug="chillbreeze",
                name="Chillbreeze Orchard",
                location="Orchard Road, Singapore",
                tags=["flagship", "beauty"],
                services=chillbreeze_services,
            )
        )
        self.add_business(
            BusinessRecord(
                business_id=1002,
                slug="chillbreeze-anna-nagar",
                name="Chillrezze Anna Nagar",
                location="Anna Nagar, Chennai",
                tags=["india", "salon"],
                services=anna_nagar_services,
            )
        )
        self.add_business(
            BusinessRecord(
                business_id=1003,
                slug="chillbreeze-adayar",
                name="Chillbreeze Adayar",
                location="Adyar, Chennai",
                tags=["india", "spa"],
                services=adayar_services,
            )
        )

    def add_business(self, record: BusinessRecord) -> None:
        self._businesses_by_id[record.business_id] = record
        self._businesses_by_slug[record.slug] = record

    def iter_businesses(self) -> Iterable[BusinessRecord]:
        return self._businesses_by_id.values()

    def get_business(self, identifier: str | int) -> Optional[BusinessRecord]:
        if isinstance(identifier, int):
            return self._businesses_by_id.get(identifier)

        identifier_str = str(identifier).strip()
        if not identifier_str:
            return None

        if identifier_str.isdigit():
            return self._businesses_by_id.get(int(identifier_str))

        normalized = identifier_str.lower()
        if normalized in self._businesses_by_slug:
            return self._businesses_by_slug[normalized]

        for record in self._businesses_by_id.values():
            name_lower = record.name.lower()
            if normalized == name_lower or normalized in name_lower:
                return record
            if normalized in record.slug:
                return record
        return None

    def search_businesses(self, query: str, limit: int) -> BusinessSearchResponse:
        normalized = query.lower()
        matches = [
            record
            for record in self._businesses_by_id.values()
            if normalized in record.name.lower()
            or normalized in record.slug
            or any(normalized in tag.lower() for tag in record.tags)
        ]
        matches.sort(key=lambda record: record.name)
        items = [
            BusinessSummary(
                business_id=record.business_id,
                name=record.name,
                location=record.location,
                tags=list(record.tags),
            )
            for record in matches[:limit]
        ]
        return BusinessSearchResponse(query=query, total=len(matches), items=items)

    def find_services(
        self, business: BusinessRecord, query: str, limit: int
    ) -> List[ServiceSummary]:
        normalized = query.lower()
        tokens = [token for token in normalized.split() if token and token not in {"just", "only", "a", "an", "the"}]
        matches = []
        for service in business.services:
            name_lower = service.name.lower()
            category_lower = service.category.lower()
            if tokens:
                if all(token in name_lower or token in category_lower for token in tokens):
                    matches.append(service)
                    continue
            if normalized in name_lower or normalized in category_lower:
                matches.append(service)
        matches.sort(key=lambda service: service.name)
        return [
            ServiceSummary(
                service_id=service.service_id,
                name=service.name,
                category=service.category,
                duration_minutes=service.duration_minutes,
                price=service.price,
            )
            for service in matches[:limit]
        ]


class AppointmentRepository(_BaseRepository):
    def __init__(self, master_data: MasterDataRepository | None = None) -> None:
        super().__init__("APT")
        self._master_data = master_data
        self._appointments: Dict[str, Dict[str, object]] = {}
        self._queue_numbers: DefaultDict[int, itertools.count] = defaultdict(
            lambda: itertools.count(1)
        )
        self._seed_defaults()

    def _seed_defaults(self) -> None:
        if not self._master_data:
            return

        chillbreeze = self._master_data.get_business("chillbreeze")
        if not chillbreeze:
            return

        seeds = [
            {
                "business_id": chillbreeze.business_id,
                "customer_name": "Alex Tan",
                "service_id": 101,
                "datetime": "2025-09-05T17:00:00+08:00",
                "status": "confirmed",
            },
            {
                "business_id": chillbreeze.business_id,
                "customer_name": "Jamie Lee",
                "service_id": 102,
                "datetime": "2025-09-06T11:30:00+08:00",
                "status": "confirmed",
            },
        ]

        for record in seeds:
            appointment_id = self._next_id()
            queue_number = f"B{next(self._queue_numbers[record['business_id']]):02d}"
            record["appointment_id"] = appointment_id
            record["queue_number"] = queue_number
            self._appointments[appointment_id] = dict(record)

        next_id = len(self._appointments) + 1
        self._counter = itertools.count(next_id)

        for business_id in {record["business_id"] for record in self._appointments.values()}:
            existing = sum(
                1
                for item in self._appointments.values()
                if item["business_id"] == business_id
            )
            self._queue_numbers[business_id] = itertools.count(existing + 1)

    async def book(self, request: AppointmentRequest) -> AppointmentResponse:
        requested_dt = self._parse_datetime(request.datetime)
        if requested_dt and self._has_conflict(request.business_id, requested_dt):
            suggestions = self._suggest_alternative_slots(request.business_id, requested_dt)
            return AppointmentResponse(
                status="conflict",
                message="The requested timeslot is unavailable for this business.",
                suggested_slots=suggestions or None,
            )

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
                service_id=int(record["service_id"]),
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

    async def get(self, appointment_id: str) -> Optional[Dict[str, object]]:
        appointment = self._appointments.get(appointment_id)
        return dict(appointment) if appointment is not None else None

    @staticmethod
    def _parse_datetime(value: str) -> Optional[datetime]:
        try:
            normalized = value.replace("Z", "+00:00")
            return datetime.fromisoformat(normalized)
        except ValueError:
            return None

    @staticmethod
    def _normalize_dt(dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    def _has_conflict(self, business_id: int, candidate: datetime) -> bool:
        candidate_norm = self._normalize_dt(candidate)
        for record in self._appointments.values():
            if record["business_id"] != business_id:
                continue
            existing_dt = self._parse_datetime(str(record["datetime"]))
            if not existing_dt:
                continue
            if self._normalize_dt(existing_dt) == candidate_norm:
                return True
        return False

    def _suggest_alternative_slots(
        self, business_id: int, requested_dt: datetime, limit: int = 3
    ) -> List[str]:
        offsets = [
            timedelta(minutes=30),
            timedelta(minutes=60),
            timedelta(minutes=-30),
            timedelta(minutes=90),
            timedelta(minutes=-60),
            timedelta(minutes=120),
        ]
        suggestions: List[str] = []
        seen: set[str] = set()
        for delta in offsets:
            candidate = requested_dt + delta
            if self._has_conflict(business_id, candidate):
                continue
            iso_value = candidate.isoformat()
            if iso_value in seen:
                continue
            suggestions.append(iso_value)
            seen.add(iso_value)
            if len(suggestions) >= limit:
                break
        return suggestions


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

    async def list(self, business_id: Optional[int] = None) -> List[Dict[str, object]]:
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
            next_action="Schedule a follow-up call or message with this lead within 24 hours.",
            follow_up_required=True,
        )

    async def list(self, business_id: Optional[int] = None) -> List[Dict[str, object]]:
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
    master_data: MasterDataRepository
    appointments: AppointmentRepository
    invoices: InvoiceRepository
    leads: LeadRepository
    campaigns: CampaignRepository
    analytics: AnalyticsRepository


_mock_store: Optional[MockDataStore] = None


def get_mock_store() -> MockDataStore:
    global _mock_store
    if _mock_store is None:
        master_data = MasterDataRepository()
        appointments = AppointmentRepository(master_data)
        invoices = InvoiceRepository()
        leads = LeadRepository()
        campaigns = CampaignRepository()
        analytics = AnalyticsRepository(appointments, invoices)
        _mock_store = MockDataStore(
            master_data=master_data,
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
