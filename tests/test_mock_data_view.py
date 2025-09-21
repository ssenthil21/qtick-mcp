from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from app.main import app
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
                business_id="chillbreeze",
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
