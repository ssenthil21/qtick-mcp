import asyncio
import os
import sys
from unittest.mock import AsyncMock

import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.schemas.analytics import AnalyticsRequest
from app.schemas.appointment import AppointmentRequest, AppointmentListRequest
from app.schemas.billing import InvoiceRequest, LineItem
from app.schemas.campaign import CampaignRequest
from app.schemas.lead import LeadCreateRequest
from app.services.analytics import AnalyticsService
from app.services.appointment import AppointmentService
from app.services.campaign import CampaignService
from app.services.invoice import InvoiceService
from app.services.leads import LeadService


class MockLatencyClient:
    """Client stub that records simulate_latency calls."""

    def __init__(self) -> None:
        self.use_mock_data = True
        self.latency_called = False

    async def simulate_latency(self) -> None:
        self.latency_called = True


def test_appointment_service_book_mock_data_returns_static_response():
    client = MockLatencyClient()
    service = AppointmentService(client)

    request = AppointmentRequest(
        business_id="biz-123",
        customer_name="Jamie",
        service_id="svc-haircut",
        datetime="2025-09-06T17:00:00+08:00",
    )

    response = asyncio.run(service.book(request))

    assert client.latency_called is True
    assert response.status == "confirmed"
    assert response.appointment_id == "APT-33451"
    assert response.queue_number == "B17"


def test_appointment_service_list_mock_data_paginates_items():
    client = MockLatencyClient()
    service = AppointmentService(client)

    request = AppointmentListRequest(
        business_id="biz-123",
        page=2,
        page_size=1,
    )

    response = asyncio.run(service.list(request))

    assert client.latency_called is True
    assert response.total == 2
    assert response.page == 2
    assert response.page_size == 1
    assert len(response.items) == 1
    assert response.items[0].appointment_id == "APT-33452"
    assert response.items[0].status == "pending"


def test_appointment_service_book_real_mode_invokes_client_post():
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


def test_invoice_service_mock_data_computes_totals_with_tax():
    client = MockLatencyClient()
    service = InvoiceService(client)

    request = InvoiceRequest(
        business_id="biz-123",
        customer_name="Jamie",
        items=[
            LineItem(description="Haircut", quantity=2, unit_price=30.0, tax_rate=0.08),
            LineItem(description="Facial", quantity=1, price=100.0),
        ],
        currency="SGD",
    )

    response = asyncio.run(service.create(request))

    assert client.latency_called is True
    assert response.invoice_id == "INV-10001"
    assert response.total == pytest.approx(164.8)
    assert response.currency == "SGD"
    assert response.payment_link.endswith("/INV-10001")
    assert response.status == "created"


def test_invoice_service_real_mode_invokes_client_post():
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


def test_lead_service_mock_data_returns_static_lead():
    client = MockLatencyClient()
    service = LeadService(client)

    request = LeadCreateRequest(business_id="biz-123", name="Morgan")

    response = asyncio.run(service.create(request))

    assert client.latency_called is True
    assert response.lead_id == "LEAD-90001"
    assert response.status == "new"


def test_campaign_service_mock_data_returns_delivery_time():
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

    assert client.latency_called is True
    assert response.status == "sent"
    assert response.delivery_time.endswith("+08:00")


def test_analytics_service_mock_data_returns_summary():
    client = MockLatencyClient()
    service = AnalyticsService(client)

    request = AnalyticsRequest(business_id="biz-123", metrics=["footfall"], period="weekly")

    response = asyncio.run(service.generate_report(request))

    assert client.latency_called is True
    assert response.footfall == 42
    assert response.revenue.startswith("SGD ")
    assert response.report_generated_at.endswith("+08:00")


def test_analytics_service_real_mode_invokes_client_post():
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
