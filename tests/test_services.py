import asyncio
import os
import sys
from unittest.mock import AsyncMock

import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.schemas.analytics import AnalyticsRequest
from app.schemas.appointment import AppointmentListRequest, AppointmentRequest
from datetime import datetime, timezone

from app.schemas.billing import (
    InvoiceListRequest,
    InvoicePaymentRequest,
    InvoiceRequest,
    LineItem,
)
from app.schemas.campaign import CampaignRequest
from app.schemas.business import BusinessSearchRequest, ServiceLookupRequest
from app.schemas.live_ops import LiveOpsRequest
from app.schemas.lead import LeadCreateRequest, LeadListRequest
from app.services.analytics import AnalyticsService
from app.services.appointment import AppointmentService
from app.services.business import BusinessDirectoryService
from app.services.campaign import CampaignService
from app.services.invoice import InvoiceService
from app.services.leads import LeadService
from app.services.live_ops import LiveOperationsService
from app.services.mock_store import get_mock_store, reset_mock_store


GENERIC_BUSINESS_ID = 4321
ANALYTICS_BUSINESS_ID = 6789
LEADS_BUSINESS_ID = 5555
REMOTE_BUSINESS_ID = 9999
INVOICE_BUSINESS_ID = 3210
SEED_CHILLBREEZE_ID = 1001
REPORT_BUSINESS_ID = 5678


@pytest.fixture(autouse=True)
def _reset_store() -> None:
    reset_mock_store()
    yield
    reset_mock_store()


class MockLatencyClient:
    """Client stub that records simulate_latency calls."""

    def __init__(self) -> None:
        self.use_mock_data = True
        self.latency_called = False

    async def simulate_latency(self) -> None:
        self.latency_called = True


def test_mock_appointment_service_persists_records() -> None:
    client = MockLatencyClient()
    service = AppointmentService(client)

    first_request = AppointmentRequest(
        business_id=GENERIC_BUSINESS_ID,
        customer_name="Jamie",
        service_id=101,
        datetime="2025-09-06T17:00:00+08:00",
    )
    second_request = AppointmentRequest(
        business_id=GENERIC_BUSINESS_ID,
        customer_name="Alex",
        service_id=202,
        datetime="2025-09-06T18:30:00+08:00",
    )

    first_response = asyncio.run(service.book(first_request))
    second_response = asyncio.run(service.book(second_request))

    assert client.latency_called is True
    assert first_response.appointment_id.startswith("APT-")
    assert first_response.queue_number == "B01"
    assert second_response.queue_number == "B02"

    list_request = AppointmentListRequest(business_id=GENERIC_BUSINESS_ID, page=1, page_size=10)
    list_response = asyncio.run(service.list(list_request))

    assert list_response.total == 2
    assert len(list_response.items) == 2
    assert {item.customer_name for item in list_response.items} == {"Jamie", "Alex"}

    store = get_mock_store()
    stored_first = asyncio.run(store.appointments.get(first_response.appointment_id))
    stored_second = asyncio.run(store.appointments.get(second_response.appointment_id))

    assert stored_first and stored_first["customer_name"] == "Jamie"
    assert stored_second and stored_second["customer_name"] == "Alex"


def test_booking_conflict_returns_suggestions() -> None:
    client = MockLatencyClient()
    service = AppointmentService(client)

    conflict_time = "2025-09-05T17:00:00+08:00"
    request = AppointmentRequest(
        business_id=SEED_CHILLBREEZE_ID,
        customer_name="Taylor",
        service_id=101,
        datetime=conflict_time,
    )

    response = asyncio.run(service.book(request))

    assert response.status == "conflict"
    assert response.appointment_id is None
    assert response.queue_number is None
    assert response.suggested_slots is not None and len(response.suggested_slots) > 0
    assert all(slot != conflict_time for slot in response.suggested_slots)


def test_mock_invoice_and_analytics_use_shared_store() -> None:
    client = MockLatencyClient()
    appointments = AppointmentService(client)
    invoices = InvoiceService(client)
    analytics = AnalyticsService(client)

    business_id = ANALYTICS_BUSINESS_ID

    asyncio.run(
        appointments.book(
            AppointmentRequest(
                business_id=business_id,
                customer_name="Taylor",
                service_id=401,
                datetime="2025-09-07T11:00:00+08:00",
            )
        )
    )
    asyncio.run(
        appointments.book(
            AppointmentRequest(
                business_id=business_id,
                customer_name="Jordan",
                service_id=402,
                datetime="2025-09-07T12:30:00+08:00",
            )
        )
    )

    invoice_request = InvoiceRequest(
        business_id=business_id,
        customer_name="Taylor",
        items=[
            LineItem(description="Haircut", quantity=2, unit_price=30.0, tax_rate=0.08),
            LineItem(description="Facial", quantity=1, price=100.0),
        ],
        currency="SGD",
    )
    invoice_response = asyncio.run(invoices.create(invoice_request))

    assert invoice_response.invoice_id.startswith("INV-")
    assert invoice_response.total == pytest.approx(164.8)

    store = get_mock_store()
    stored_invoice = asyncio.run(store.invoices.get(invoice_response.invoice_id))
    assert stored_invoice and stored_invoice["total"] == pytest.approx(164.8)

    analytics_request = AnalyticsRequest(
        business_id=business_id,
        metrics=["footfall", "revenue"],
        period="weekly",
    )
    analytics_response = asyncio.run(analytics.generate_report(analytics_request))

    assert analytics_response.footfall == 2
    assert analytics_response.revenue == "SGD 164.80"


def test_service_lookup_returns_candidates_when_business_name_ambiguous() -> None:
    client = MockLatencyClient()
    service = BusinessDirectoryService(client)

    request = ServiceLookupRequest(service_name="Signature Haircut", business_name="Chillbreeze")
    response = asyncio.run(service.lookup_service(request))

    assert response.business is None
    assert response.business_candidates is not None
    assert len(response.business_candidates) > 1
    assert response.message and "Multiple businesses" in response.message


def test_business_search_returns_suggestions_for_multiple_matches() -> None:
    client = MockLatencyClient()
    service = BusinessDirectoryService(client)

    request = BusinessSearchRequest(query="Chillbreeze")
    response = asyncio.run(service.search(request))

    assert response.total == 3
    assert response.suggested_business_names is not None
    assert {
        "Chillbreeze Adayar",
        "Chillbreeze Anna Nagar",
        "Chillbreeze Orchard",
    } == set(response.suggested_business_names)
    assert response.message and "Multiple businesses" in response.message
    for name in response.suggested_business_names:
        assert name in response.message


def test_service_lookup_lists_businesses_for_service_only_query() -> None:
    client = MockLatencyClient()
    service = BusinessDirectoryService(client)

    request = ServiceLookupRequest(service_name="Haircut", limit=5)
    response = asyncio.run(service.lookup_service(request))

    assert response.business is None or response.service_matches is not None
    assert response.service_matches is not None
    assert len(response.service_matches) >= 1
    business_names = {match.business.name for match in response.service_matches}
    assert {
        "Chillbreeze Orchard",
        "Chillbreeze Anna Nagar",
        "Chillbreeze Adayar",
    }.issubset(business_names)
    expected_keywords = {
        "Chillbreeze Orchard": {"men's haircut", "baby haircut"},
        "Chillbreeze Anna Nagar": {"men's haircut", "baby haircut"},
        "Chillbreeze Adayar": {"men's haircut", "baby haircut"},
    }
    for match in response.service_matches:
        if match.business.name not in business_names:
            continue
        names = {service.name.lower() for service in match.services}
        assert any("haircut" in name for name in names)
        for keyword in expected_keywords.get(match.business.name, set()):
            assert any(keyword in name for name in names)


def test_service_lookup_supports_new_business_categories() -> None:
    client = MockLatencyClient()
    service = BusinessDirectoryService(client)

    laundry_response = asyncio.run(
        service.lookup_service(ServiceLookupRequest(service_name="Laundry"))
    )
    assert laundry_response.business is not None
    assert laundry_response.business.name == "FreshFold Laundry"
    assert laundry_response.matches is not None
    assert any(
        service.name.lower().startswith("express") or "laundry" in service.category.lower()
        for service in laundry_response.matches
    )

    takeaway_response = asyncio.run(
        service.lookup_service(
            ServiceLookupRequest(service_name="Food Take Away")
        )
    )
    assert takeaway_response.business is not None
    assert takeaway_response.business.name == "QuickBite Takeaway"
    assert takeaway_response.matches is not None
    assert any(
        "takeaway" in service.name.lower() for service in takeaway_response.matches
    )

    turf_response = asyncio.run(
        service.lookup_service(ServiceLookupRequest(service_name="Turf"))
    )
    assert turf_response.business is not None
    assert turf_response.business.name == "Greenfield Turf Club"
    assert turf_response.matches is not None
    assert any(
        "turf" in service.name.lower() or "sports" in service.category.lower()
        for service in turf_response.matches
    )


def test_mark_invoice_paid_triggers_review_request() -> None:
    client = MockLatencyClient()
    invoices = InvoiceService(client)

    invoice_request = InvoiceRequest(
        business_id=SEED_CHILLBREEZE_ID,
        customer_name="Jordan",
        items=[LineItem(description="Spa", quantity=1, unit_price=88.0)],
    )
    invoice = asyncio.run(invoices.create(invoice_request))

    payment_request = InvoicePaymentRequest(
        invoice_id=invoice.invoice_id,
        paid_at=datetime.now(timezone.utc).isoformat(),
    )
    payment_response = asyncio.run(invoices.mark_paid(payment_request))

    assert payment_response.status == "paid"
    assert payment_response.review_request_id is not None

    store = get_mock_store()
    stored_review = asyncio.run(
        store.reviews.get(payment_response.review_request_id)
    )
    assert stored_review is not None
    assert stored_review["invoice_id"] == invoice.invoice_id


def test_live_operations_events_include_recent_activity() -> None:
    client = MockLatencyClient()
    appointments = AppointmentService(client)
    invoices = InvoiceService(client)
    leads = LeadService(client)
    live_ops = LiveOperationsService(client)

    now = datetime.now(timezone.utc)
    appointment_time = now.replace(hour=9, minute=30, second=0, microsecond=0)

    asyncio.run(
        appointments.book(
            AppointmentRequest(
                business_id=SEED_CHILLBREEZE_ID,
                customer_name="Jamie",
                service_id=101,
                datetime=appointment_time.isoformat(),
            )
        )
    )

    invoice = asyncio.run(
        invoices.create(
            InvoiceRequest(
                business_id=SEED_CHILLBREEZE_ID,
                customer_name="Jamie",
                items=[LineItem(description="Haircut", quantity=1, unit_price=42.0)],
            )
        )
    )

    asyncio.run(
        invoices.mark_paid(
            InvoicePaymentRequest(
                invoice_id=invoice.invoice_id,
                paid_at=now.isoformat(),
            )
        )
    )

    asyncio.run(
        leads.create(
            LeadCreateRequest(
                business_id=SEED_CHILLBREEZE_ID,
                name="Morgan",
                email="morgan@example.com",
            )
        )
    )

    response = asyncio.run(
        live_ops.events(
            LiveOpsRequest(
                business_id=SEED_CHILLBREEZE_ID,
                date=now.date().isoformat(),
            )
        )
    )

    assert response.business.business_id == SEED_CHILLBREEZE_ID
    assert response.date == now.date().isoformat()
    assert response.total_events >= 3
    event_types = {event.event_type for event in response.events}
    assert {"appointment", "invoice", "review"}.issubset(event_types)
    assert any(event.event_type == "lead" for event in response.events)


def test_lead_repository_stores_created_leads() -> None:
    client = MockLatencyClient()
    service = LeadService(client)

    request = LeadCreateRequest(business_id=LEADS_BUSINESS_ID, name="Morgan", email="m@example.com")
    response = asyncio.run(service.create(request))

    assert response.lead_id.startswith("LEAD-")
    assert response.follow_up_required is True
    assert "follow-up" in response.next_action.lower()

    store = get_mock_store()
    stored = asyncio.run(store.leads.get(response.lead_id))
    assert stored and stored["email"] == "m@example.com"

    leads = asyncio.run(store.leads.list(LEADS_BUSINESS_ID))
    assert len(leads) == 1
    assert leads[0]["lead_id"] == response.lead_id
    assert leads[0]["email"] == "m@example.com"


def test_campaign_repository_tracks_sent_messages() -> None:
    client = MockLatencyClient()
    service = CampaignService(client)

    request = CampaignRequest(
        customer_name="Sam",
        phone_number="12345678",
        message_template="Hello {name}",
        offer_code="OFFER1",
        expiry="2025-09-07",
    )

    response = asyncio.run(service.send_whatsapp(request))

    assert response.status == "sent"

    store = get_mock_store()
    campaigns = asyncio.run(store.campaigns.list())
    assert len(campaigns) == 1
    assert campaigns[0]["phone_number"] == "12345678"
    stored = asyncio.run(store.campaigns.get(campaigns[0]["campaign_id"]))
    assert stored and stored["offer_code"] == "OFFER1"


def test_appointment_service_book_real_mode_invokes_client_post() -> None:
    request = AppointmentRequest(
        business_id=REMOTE_BUSINESS_ID,
        customer_name="Alex",
        service_id=501,
        datetime="2025-09-06T17:00:00+08:00",
    )

    client = type(
        "ClientStub",
        (),
        {
            "use_mock_data": False,
            "post": AsyncMock(
                return_value={
                    "status": "confirmed",
                    "appointment_id": "APT-1",
                    "queue_number": "A1",
                }
            ),
        },
    )()

    service = AppointmentService(client)
    response = asyncio.run(service.book(request))

    client.post.assert_awaited_once_with("/appointments/book", request.model_dump())
    assert response.appointment_id == "APT-1"
    assert response.queue_number == "A1"


def test_seeded_chillbreeze_appointments_available() -> None:
    client = MockLatencyClient()
    service = AppointmentService(client)

    list_request = AppointmentListRequest(business_id=SEED_CHILLBREEZE_ID, page=1, page_size=10)
    response = asyncio.run(service.list(list_request))

    assert response.total >= 2
    assert all(isinstance(item.service_id, int) for item in response.items)


def test_business_directory_search_and_lookup() -> None:
    client = MockLatencyClient()
    service = BusinessDirectoryService(client)

    search_request = BusinessSearchRequest(query="chillbreeze", limit=5)
    search_response = asyncio.run(service.search(search_request))

    assert search_response.total >= 3
    names = {item.name for item in search_response.items}
    assert "Chillbreeze Anna Nagar" in names
    assert "Chillbreeze Adayar" in names
    assert search_response.message is not None
    assert "Multiple businesses" in search_response.message

    laundry_search = asyncio.run(
        service.search(BusinessSearchRequest(query="laundry", limit=5))
    )
    assert laundry_search.total >= 1
    assert any(item.name == "FreshFold Laundry" for item in laundry_search.items)

    takeaway_search = asyncio.run(
        service.search(BusinessSearchRequest(query="takeaway", limit=5))
    )
    assert takeaway_search.total >= 1
    assert any(item.name == "QuickBite Takeaway" for item in takeaway_search.items)

    turf_search = asyncio.run(
        service.search(BusinessSearchRequest(query="turf", limit=5))
    )
    assert turf_search.total >= 1
    assert any(item.name == "Greenfield Turf Club" for item in turf_search.items)

    lookup_request = ServiceLookupRequest(
        business_name="Chillbreeze",
        service_name="haircut",
    )
    lookup_response = asyncio.run(service.lookup_service(lookup_request))

    assert lookup_response.business is None
    assert lookup_response.business_candidates is not None
    assert len(lookup_response.business_candidates) >= 2
    assert lookup_response.message is not None
    assert "Multiple businesses matched" in lookup_response.message


def test_haircut_lookup_with_space_prompts_for_specific_service() -> None:
    client = MockLatencyClient()
    service = BusinessDirectoryService(client)

    lookup_request = ServiceLookupRequest(
        business_name="Chillbreeze",
        service_name="hair cut",
    )
    lookup_response = asyncio.run(service.lookup_service(lookup_request))

    assert lookup_response.business is None
    assert lookup_response.business_candidates is not None
    assert any("Chillbreeze" in item.name for item in lookup_response.business_candidates)
    assert lookup_response.message is not None
    assert "Multiple businesses matched" in lookup_response.message


def test_lead_create_prompts_follow_up_and_list() -> None:
    client = MockLatencyClient()
    service = LeadService(client)

    request = LeadCreateRequest(
        business_id=SEED_CHILLBREEZE_ID,
        name="Priya",
        phone="1234",
        email="priya@example.com",
    )
    response = asyncio.run(service.create(request))

    assert response.follow_up_required is True
    assert "follow-up" in response.next_action.lower()

    list_request = LeadListRequest(business_id=SEED_CHILLBREEZE_ID)
    list_response = asyncio.run(service.list(list_request))

    assert list_response.total >= 1
    assert any(item.lead_id == response.lead_id for item in list_response.items)


def test_invoice_list_returns_created_records() -> None:
    client = MockLatencyClient()
    service = InvoiceService(client)

    create_request = InvoiceRequest(
        business_id=SEED_CHILLBREEZE_ID,
        customer_name="Alex",
        items=[LineItem(description="Haircut", quantity=1, unit_price=30.0)],
    )
    created = asyncio.run(service.create(create_request))

    list_request = InvoiceListRequest(business_id=SEED_CHILLBREEZE_ID)
    list_response = asyncio.run(service.list(list_request))

    assert list_response.total >= 1
    assert any(item.invoice_id == created.invoice_id for item in list_response.items)


def test_invoice_service_real_mode_invokes_client_post() -> None:
    request = InvoiceRequest(
        business_id=INVOICE_BUSINESS_ID,
        customer_name="Taylor",
        items=[LineItem(description="Package", quantity=1, unit_price=199.0)],
    )

    payload = {
        "invoice_id": "INV-20002",
        "total": 199.0,
        "currency": "SGD",
        "created_at": "2025-09-05T15:03:10+08:00",
        "payment_link": "https://pay.qtick.co/INV-20002",
        "status": "created",
    }

    client = type(
        "ClientStub",
        (),
        {
            "use_mock_data": False,
            "post": AsyncMock(return_value=payload),
        },
    )()

    service = InvoiceService(client)
    response = asyncio.run(service.create(request))

    client.post.assert_awaited_once_with("/invoices", request.model_dump())
    assert response.invoice_id == "INV-20002"
    assert response.payment_link == "https://pay.qtick.co/INV-20002"


def test_analytics_service_real_mode_invokes_client_post() -> None:
    request = AnalyticsRequest(business_id=REPORT_BUSINESS_ID, metrics=["revenue"], period="monthly")

    payload = {
        "footfall": 120,
        "revenue": "SGD 5,000",
        "report_generated_at": "2025-09-05T15:03:10+08:00",
    }

    client = type(
        "ClientStub",
        (),
        {
            "use_mock_data": False,
            "post": AsyncMock(return_value=payload),
        },
    )()

    service = AnalyticsService(client)
    response = asyncio.run(service.generate_report(request))

    client.post.assert_awaited_once_with("/analytics/report", request.model_dump())
    assert response.footfall == 120
    assert response.revenue == "SGD 5,000"
