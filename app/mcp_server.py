
# app/mcp_server.py
from mcp.server.fastmcp import FastMCP
import os, requests

BASE = os.getenv("MCP_PUBLIC_BASE", "http://127.0.0.1:8000")
API_KEY = os.getenv("QTF_API_KEY")

mcp = FastMCP("qtick_mcp")

def _post(path: str, payload: dict):
    headers = {"X-API-Key": API_KEY} if API_KEY else None
    resp = requests.post(f"{BASE}{path}", json=payload, timeout=30, headers=headers)
    resp.raise_for_status()
    return resp.json()

@mcp.tool()
def appointments_book(business_id: str, customer_name: str, service_id: str, datetime: str) -> dict:
    """Book an appointment in QTick."""
    return _post("/tools/appointment/book", {
        "business_id": business_id,
        "customer_name": customer_name,
        "service_id": service_id,
        "datetime": datetime
    })

@mcp.tool()
def appointments_list(business_id: str, date_from: str | None = None, date_to: str | None = None,
                      status: str | None = None, page: int = 1, page_size: int = 20) -> dict:
    """List appointments for a business with optional filters and pagination."""
    return _post("/tools/appointment/list", {
        "business_id": business_id, "date_from": date_from, "date_to": date_to,
        "status": status, "page": page, "page_size": page_size
    })

@mcp.tool()
def invoice_create(business_id: str, customer_name: str, items: list[dict], currency: str = "SGD",
                   appointment_id: str | None = None, notes: str | None = None) -> dict:
    """Create an invoice with line items."""
    return _post("/tools/invoice/create", {
        "business_id": business_id, "customer_name": customer_name, "items": items,
        "currency": currency, "appointment_id": appointment_id, "notes": notes
    })

@mcp.tool()
def leads_create(business_id: str, name: str, phone: str | None = None, email: str | None = None,
                 source: str = "manual", notes: str | None = None) -> dict:
    """Create a new customer lead."""
    return _post("/tools/leads/create", {
        "business_id": business_id, "name": name, "phone": phone,
        "email": email, "source": source, "notes": notes
    })

@mcp.tool()
def campaign_send_whatsapp(customer_name: str, phone_number: str, message_template: str,
                           offer_code: str | None = None, expiry: str | None = None) -> dict:
    """Send a WhatsApp campaign message to a customer."""
    return _post("/tools/campaign/sendWhatsApp", {
        "customer_name": customer_name, "phone_number": phone_number,
        "message_template": message_template, "offer_code": offer_code, "expiry": expiry
    })

@mcp.tool()
def analytics_report(business_id: str, metrics: list[str], period: str) -> dict:
    """Fetch analytics for a business over a period."""
    return _post("/tools/analytics/report", {
        "business_id": business_id, "metrics": metrics, "period": period
    })
