from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.billing import InvoiceRequest, LineItem
from app.schemas.lead import LeadCreateRequest
from app.services.mock_store import get_mock_store, reset_mock_store


def test_mock_data_view_renders_seed_data() -> None:
    reset_mock_store()
    client = TestClient(app)

    response = client.get("/mock-data")
    assert response.status_code == 200
    body = response.text

    assert "Mock Data Overview" in body
    assert "Chillbreeze Orchard" in body  # seeded business name
    assert "Signature Haircut" in body  # seeded service name
    assert "No records found." in body  # empty sections show message


def test_mock_data_view_includes_created_records() -> None:
    reset_mock_store()
    store = get_mock_store()

    asyncio.run(
        store.leads.create(
            LeadCreateRequest(
                business_id=1001,
                name="Test Lead",
                phone="1234567",
                email="lead@example.com",
                source="test",
                notes="Follow up soon",
            )
        )
    )

    client = TestClient(app)
    response = client.get("/mock-data")
    assert response.status_code == 200

    body = response.text
    assert "Test Lead" in body
    assert "lead@example.com" in body


def test_mock_data_view_displays_invoices() -> None:
    reset_mock_store()
    store = get_mock_store()

    invoice = asyncio.run(
        store.invoices.create(
            InvoiceRequest(
                business_id=1001,
                customer_name="Jane Client",
                items=[
                    LineItem(
                        description="Signature Haircut",
                        quantity=1,
                        unit_price=38.0,
                        tax_rate=0.08,
                    )
                ],
            )
        )
    )

    client = TestClient(app)
    response = client.get("/mock-data")
    assert response.status_code == 200

    body = response.text
    assert invoice.invoice_id in body
    assert f"{invoice.total:.2f}" in body


def test_delete_mock_data_record_removes_entry() -> None:
    reset_mock_store()
    store = get_mock_store()

    lead_response = asyncio.run(
        store.leads.create(
            LeadCreateRequest(
                business_id=1001,
                name="Delete Me",
                phone="555-0000",
                email="delete@example.com",
                source="test",
            )
        )
    )

    client = TestClient(app)
    delete_response = client.delete(f"/mock-data/leads/{lead_response.lead_id}")

    assert delete_response.status_code == 200
    payload = delete_response.json()
    assert payload["status"] == "deleted"
    assert payload["record_id"] == lead_response.lead_id

    remaining = asyncio.run(store.leads.get(lead_response.lead_id))
    assert remaining is None


def test_delete_mock_data_unknown_collection_returns_404() -> None:
    reset_mock_store()
    client = TestClient(app)

    response = client.delete("/mock-data/unknown/123")

    assert response.status_code == 404
    assert response.json()["detail"] == "Unsupported mock data collection"
