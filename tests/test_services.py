import asyncio
import os
import sys
from unittest.mock import AsyncMock

import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.schemas.analytics import AnalyticsRequest
from app.schemas.appointment import AppointmentListRequest, AppointmentRequest
from app.schemas.billing import InvoiceRequest, LineItem
from app.schemas.campaign import CampaignRequest
from app.schemas.lead import LeadCreateRequest
from app.services.analytics import AnalyticsService
from app.services.appointment import AppointmentService
from app.services.campaign import CampaignService
from app.services.invoice import InvoiceService
from app.services.leads import LeadService
from app.services.mock_store import get_mock_store, reset_mock_store


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
        business_id="biz-123",
        customer_name="Jamie",
        service_id="svc-haircut",
        datetime="2025-09-06T17:00:00+08:00",
    )
    second_request = AppointmentRequest(
        business_id="biz-123",
        customer_name="Alex",
        service_id="svc-facial",
        datetime="2025-09-06T18:30:00+08:00",
    )

    first_response = asyncio.run(service.book(first_request))
    second_response = asyncio.run(service.book(second_request))

    assert client.latency_called is True
    assert first_response.appointment_id.startswith("APT-")
    assert first_response.queue_number == "B01"
    assert second_response.queue_number == "B02"

    list_request = AppointmentListRequest(business_id="biz-123", page=1, page_size=10)
    list_response = asyncio.run(service.list(list_request))

    assert list_response.total == 2
    assert len(list_response.items) == 2
    assert {item.customer_name for item in list_response.items} == {"Jamie", "Alex"}

    store = get_mock_store()
    stored_first = asyncio.run(store.appointments.get(first_response.appointment_id))
    stored_second = asyncio.run(store.appointments.get(second_response.appointment_id))

    assert stored_first and stored_first["customer_name"] == "Jamie"
    assert stored_second and stored_second["customer_name"] == "Alex"


def test_mock_invoice_and_analytics_use_shared_store() -> None:
    client = MockLatencyClient()
    appointments = AppointmentService(client)
    invoices = InvoiceService(client)
    analytics = AnalyticsService(client)

    business_id = "biz-analytics"

    asyncio.run(
        appointments.book(
            AppointmentRequest(
                business_id=business_id,
                customer_name="Taylor",
                service_id="svc-cut",
                datetime="2025-09-07T11:00:00+08:00",
            )
        )
    )
    asyncio.run(
        appointments.book(
            AppointmentRequest(
                business_id=business_id,
                customer_name="Jordan",
                service_id="svc-spa",
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


def test_lead_repository_stores_created_leads() -> None:
    client = MockLatencyClient()
    service = LeadService(client)

    request = LeadCreateRequest(business_id="biz-555", name="Morgan", email="m@example.com")
    response = asyncio.run(service.create(request))

    assert response.lead_id.startswith("LEAD-")

    store = get_mock_store()
    stored = asyncio.run(store.leads.get(response.lead_id))
    assert stored and stored["email"] == "m@example.com"

    leads = asyncio.run(store.leads.list("biz-555"))
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
        business_id="biz-999",
        customer_name="Alex",
        service_id="svc-cut",
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


def test_invoice_service_real_mode_invokes_client_post() -> None:
    request = InvoiceRequest(
        business_id="biz-321",
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
    request = AnalyticsRequest(business_id="biz-567", metrics=["revenue"], period="monthly")

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
