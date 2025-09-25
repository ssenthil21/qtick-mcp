import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.tools.agent import summarize_tool_result


def test_summarize_appointment_booking_returns_datapoints() -> None:
    tool_name, data_points = summarize_tool_result(
        "appointment_book",
        {
            "business_id": 1001,
            "customer_name": "Alex",
            "service_id": 101,
            "datetime": "2025-09-05T17:00:00+08:00",
        },
        {
            "status": "confirmed",
            "appointment_id": "APT-00003",
            "queue_number": "B01",
        },
    )

    assert tool_name == "Appointment"
    assert data_points[0]["appointmentId"] == "APT-00003"
    assert data_points[0]["customer"] == "Alex"
    assert data_points[0]["queueNumber"] == "B01"


def test_summarize_appointment_conflict_includes_suggestions() -> None:
    _, data_points = summarize_tool_result(
        "appointment_book",
        {
            "business_id": 1001,
            "customer_name": "Jamie",
            "service_id": 102,
            "datetime": "2025-09-05T17:00:00+08:00",
        },
        {
            "status": "conflict",
            "message": "Requested slot unavailable",
            "suggested_slots": [
                "2025-09-05T17:30:00+08:00",
                "2025-09-05T18:00:00+08:00",
            ],
        },
    )

    payload = data_points[0]
    assert payload["status"] == "conflict"
    assert "suggestedSlots" in payload and len(payload["suggestedSlots"]) == 2
    assert payload["message"] == "Requested slot unavailable"


def test_summarize_invoice_creation_contains_items() -> None:
    tool_name, data_points = summarize_tool_result(
        "invoice_create",
        {
            "business_id": 2001,
            "customer_name": "Taylor",
            "items": [
                {
                    "description": "Haircut",
                    "quantity": 1,
                    "unit_price": 25.0,
                    "tax_rate": 0.08,
                },
                {
                    "description": "Serum",
                    "quantity": 2,
                    "price": 12.5,
                },
            ],
            "currency": "SGD",
        },
        {
            "invoice_id": "INV-00001",
            "total": 52.0,
            "currency": "SGD",
            "status": "created",
            "payment_link": "https://pay.qtick.co/INV-00001",
            "created_at": "2025-09-05T12:00:00+08:00",
        },
    )

    assert tool_name == "Invoice"
    payload = data_points[0]
    assert payload["invoiceId"] == "INV-00001"
    assert payload["total"] == 52.0
    assert payload["currency"] == "SGD"
    assert payload["customer"] == "Taylor"
    assert payload["businessId"] == 2001
    assert len(payload["items"]) == 2
    assert payload["items"][0]["description"] == "Haircut"


def test_summarize_service_lookup_groups_matches() -> None:
    _, data_points = summarize_tool_result(
        "business_service_lookup",
        None,
        {
            "query": "Haircut",
            "business": {
                "business_id": 1001,
                "name": "Chillbreeze Orchard",
                "location": "Orchard Road",
                "tags": ["flagship"],
            },
            "matches": [
                {
                    "service_id": 101,
                    "name": "Signature Haircut",
                    "category": "grooming",
                    "duration_minutes": 45,
                    "price": 38.0,
                },
                {
                    "service_id": 104,
                    "name": "Kids Haircut",
                    "category": "grooming",
                    "duration_minutes": 30,
                    "price": 25.0,
                },
            ],
            "message": "Multiple services matched your search.",
            "suggested_service_names": ["Signature Haircut", "Kids Haircut"],
        },
    )

    assert len(data_points) == 1
    payload = data_points[0]
    assert payload["query"].lower() == "haircut"
    assert payload["business"]["businessId"] == 1001
    assert len(payload["matches"]) == 2
    assert payload["matches"][0]["serviceId"] == 101
    assert payload["message"].startswith("Multiple services")
    assert payload["suggestedServices"] == ["Signature Haircut", "Kids Haircut"]


def test_summarize_business_search_returns_options() -> None:
    _, data_points = summarize_tool_result(
        "business_search",
        None,
        {
            "query": "Chillbreeze",
            "total": 2,
            "items": [
                {
                    "business_id": 1001,
                    "name": "Chillbreeze Orchard",
                    "location": "Orchard Road",
                    "tags": ["flagship"],
                },
                {
                    "business_id": 1003,
                    "name": "Chillbreeze Adayar",
                    "location": "Adyar",
                    "tags": ["india"],
                },
            ],
            "message": "Multiple businesses match your search.",
        },
    )

    assert len(data_points) == 4
    summary = data_points[0]
    assert summary["query"].lower() == "chillbreeze"
    assert summary["total"] == 2

    options = data_points[1:3]
    assert {item["businessId"] for item in options} == {1001, 1003}

    message = data_points[3]
    assert message["message"].startswith("Multiple businesses match")


def test_summarize_analytics_includes_service_insights() -> None:
    _, data_points = summarize_tool_result(
        "analytics_report",
        None,
        {
            "footfall": 42,
            "revenue": "SGD 1,234.00",
            "report_generated_at": "2025-09-07T00:00:00+00:00",
            "top_appointment_service": {
                "service_id": 303,
                "name": "Men's Haircut",
                "booking_count": 12,
            },
            "highest_revenue_service": {
                "service_id": 302,
                "name": "Soothing Head Massage",
                "total_revenue": 540.0,
                "currency": "SGD",
            },
            "appointment_summary": {
                "total": 18,
                "by_status": {"confirmed": 16, "cancelled": 2},
                "unique_customers": 14,
            },
            "invoice_summary": {
                "total": 20,
                "by_status": {"paid": 15, "created": 5},
                "total_revenue": 3250.0,
                "paid_total": 2875.0,
                "outstanding_total": 375.0,
                "average_invoice_value": 162.5,
                "currency": "SGD",
                "unique_customers": 12,
            },
            "lead_summary": {
                "total": 9,
                "by_status": {"new": 7, "contacted": 2},
                "source_breakdown": {
                    "instagram": 4,
                    "referral": 3,
                    "walk-in": 2,
                },
            },
        },
    )

    assert len(data_points) == 1
    payload = data_points[0]
    top_service = payload["topAppointmentService"]
    assert top_service["serviceId"] == 303
    assert top_service["bookingCount"] == 12
    highest = payload["highestRevenueService"]
    assert highest["name"] == "Soothing Head Massage"
    assert highest["totalRevenue"] == 540.0
    appointment_summary = payload["appointmentSummary"]
    assert appointment_summary["total"] == 18
    assert appointment_summary["byStatus"]["confirmed"] == 16
    assert appointment_summary["uniqueCustomers"] == 14
    invoice_summary = payload["invoiceSummary"]
    assert invoice_summary["totalRevenue"] == 3250.0
    assert invoice_summary["outstandingTotal"] == 375.0
    assert invoice_summary["uniqueCustomers"] == 12
    lead_summary = payload["leadSummary"]
    assert lead_summary["total"] == 9
    assert lead_summary["byStatus"]["new"] == 7
    assert lead_summary["sourceBreakdown"]["instagram"] == 4
