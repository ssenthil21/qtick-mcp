from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Iterable, List, Optional

from app.clients.java import JavaServiceClient
from app.schemas.appointment import AppointmentListRequest
from app.schemas.business import BusinessSummary
from app.schemas.live_ops import LiveOpsEvent, LiveOpsRequest, LiveOpsResponse
from app.services.exceptions import ServiceError
from app.services.mock_store import (
    AppointmentRepository,
    InvoiceRepository,
    LeadRepository,
    MasterDataRepository,
    ReviewRepository,
    get_mock_store,
)

logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class LiveOperationsService:
    """Aggregate live operational events for a business."""

    def __init__(
        self,
        client: JavaServiceClient,
        *,
        master_data: MasterDataRepository | None = None,
        appointments: AppointmentRepository | None = None,
        invoices: InvoiceRepository | None = None,
        leads: LeadRepository | None = None,
        reviews: ReviewRepository | None = None,
    ) -> None:
        self._client = client
        self._master_data = master_data
        self._appointments = appointments
        self._invoices = invoices
        self._leads = leads
        self._reviews = reviews
        if self._client.use_mock_data:
            store = get_mock_store()
            self._master_data = master_data or store.master_data
            self._appointments = appointments or store.appointments
            self._invoices = invoices or store.invoices
            self._leads = leads or store.leads
            self._reviews = reviews or store.reviews

    async def events(self, request: LiveOpsRequest) -> LiveOpsResponse:
        logger.info("Fetching live operations for business %s", request.business_id)
        if self._client.use_mock_data:
            await self._client.simulate_latency()
            return await self._collect_mock_events(request)

        raise ServiceError("Live operations feed is not available in live mode yet")

    async def _collect_mock_events(self, request: LiveOpsRequest) -> LiveOpsResponse:
        if not all([self._master_data, self._appointments, self._invoices, self._leads, self._reviews]):
            raise RuntimeError("Mock repositories for live operations are not configured")

        business_record = self._master_data.get_business(request.business_id)
        if not business_record:
            raise ServiceError(f"Business '{request.business_id}' not found")

        target_date = self._resolve_target_date(request.date)
        events: List[LiveOpsEvent] = []

        appointments = await self._appointments.list(
            AppointmentListRequest(
                business_id=business_record.business_id,
                page=1,
                page_size=200,
            )
        )
        events.extend(self._build_appointment_events(appointments.items, target_date))

        invoice_records = await self._invoices.list(business_record.business_id)
        events.extend(self._build_invoice_events(invoice_records, target_date))

        lead_records = await self._leads.list(business_record.business_id)
        events.extend(self._build_lead_events(lead_records, target_date))

        review_records = await self._reviews.list(business_record.business_id)
        events.extend(self._build_review_events(review_records, target_date))

        events.sort(key=lambda event: event.timestamp, reverse=True)

        business_summary = BusinessSummary(
            business_id=business_record.business_id,
            name=business_record.name,
            location=business_record.location,
            tags=list(business_record.tags),
        )

        return LiveOpsResponse(
            business=business_summary,
            date=target_date.isoformat(),
            generated_at=_utc_now_iso(),
            total_events=len(events),
            events=events,
        )

    @staticmethod
    def _resolve_target_date(value: Optional[str]) -> date:
        if not value:
            return datetime.now(timezone.utc).date()
        try:
            return datetime.fromisoformat(value).date()
        except ValueError as exc:  # pragma: no cover - validation occurs at schema level
            raise ServiceError("Invalid date format. Expected YYYY-MM-DD.") from exc

    @staticmethod
    def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        try:
            normalized = value.replace("Z", "+00:00")
            return datetime.fromisoformat(normalized)
        except ValueError:
            return None

    def _build_appointment_events(
        self, appointments: Iterable, target_date: date
    ) -> List[LiveOpsEvent]:
        events: List[LiveOpsEvent] = []
        for item in appointments:
            dt = self._parse_datetime(getattr(item, "datetime", None))
            if not dt or dt.astimezone(timezone.utc).date() != target_date:
                continue
            summary = f"Appointment confirmed for {item.customer_name}"
            events.append(
                LiveOpsEvent(
                    event_type="appointment",
                    summary=summary,
                    timestamp=dt.isoformat(),
                    details={
                        "queue_number": getattr(item, "queue_number", None),
                        "status": getattr(item, "status", None),
                        "service_id": getattr(item, "service_id", None),
                    },
                )
            )
        return events

    def _build_invoice_events(
        self, invoices: Iterable[dict], target_date: date
    ) -> List[LiveOpsEvent]:
        events: List[LiveOpsEvent] = []
        for invoice in invoices:
            created_dt = self._parse_datetime(str(invoice.get("created_at")))
            if created_dt and created_dt.astimezone(timezone.utc).date() == target_date:
                customer = invoice.get("customer_name") or "customer"
                summary = f"Invoice {invoice['invoice_id']} issued to {customer}"
                events.append(
                    LiveOpsEvent(
                        event_type="invoice",
                        summary=summary,
                        timestamp=created_dt.isoformat(),
                        details={
                            "status": invoice.get("status"),
                            "total": float(invoice.get("total", 0.0)),
                            "currency": invoice.get("currency"),
                        },
                    )
                )

            paid_at = invoice.get("paid_at")
            paid_dt = self._parse_datetime(str(paid_at) if paid_at else None)
            if paid_dt and paid_dt.astimezone(timezone.utc).date() == target_date:
                summary = f"Payment received for invoice {invoice['invoice_id']}"
                events.append(
                    LiveOpsEvent(
                        event_type="invoice",
                        summary=summary,
                        timestamp=paid_dt.isoformat(),
                        details={
                            "status": "paid",
                            "total": float(invoice.get("total", 0.0)),
                            "currency": invoice.get("currency"),
                        },
                    )
                )
        return events

    def _build_lead_events(
        self, leads: Iterable[dict], target_date: date
    ) -> List[LiveOpsEvent]:
        events: List[LiveOpsEvent] = []
        for lead in leads:
            created_dt = self._parse_datetime(str(lead.get("created_at")))
            if not created_dt or created_dt.astimezone(timezone.utc).date() != target_date:
                continue
            summary = f"New lead captured: {lead.get('name', 'Prospect')}"
            events.append(
                LiveOpsEvent(
                    event_type="lead",
                    summary=summary,
                    timestamp=created_dt.isoformat(),
                    details={
                        "status": lead.get("status"),
                        "source": lead.get("source"),
                    },
                )
            )
        return events

    def _build_review_events(
        self, reviews: Iterable[dict], target_date: date
    ) -> List[LiveOpsEvent]:
        events: List[LiveOpsEvent] = []
        for review in reviews:
            requested_dt = self._parse_datetime(str(review.get("requested_at")))
            if requested_dt and requested_dt.astimezone(timezone.utc).date() == target_date:
                summary = f"Review request sent to {review.get('customer_name', 'customer')}"
                events.append(
                    LiveOpsEvent(
                        event_type="review",
                        summary=summary,
                        timestamp=requested_dt.isoformat(),
                        details={
                            "status": review.get("status"),
                            "invoice_id": review.get("invoice_id"),
                        },
                    )
                )

            completed_dt = self._parse_datetime(str(review.get("completed_at")))
            if (
                completed_dt
                and completed_dt.astimezone(timezone.utc).date() == target_date
                and review.get("rating")
            ):
                summary = (
                    f"New {review['rating']}-star review received from {review.get('customer_name', 'customer')}"
                )
                events.append(
                    LiveOpsEvent(
                        event_type="review",
                        summary=summary,
                        timestamp=completed_dt.isoformat(),
                        details={
                            "rating": review.get("rating"),
                            "feedback": review.get("feedback"),
                        },
                    )
                )
        return events
