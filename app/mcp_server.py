# app/mcp_server.py
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
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

# ---- Typed models (avoid list[dict] / dict[Any, Any]) ----
class InvoiceItem(BaseModel):
    item_id: Optional[str] = None
    description: str
    quantity: int
    unit_price: Optional[float] = None  # alias to price if you prefer
    price: Optional[float] = None       # some clients send "price" instead
    tax_rate: float = 0.0

# ---- Simple ping to confirm MCP handshake ----
@mcp.tool()
def ping() -> str:
    """Return 'pong' to confirm MCP transport is alive."""
    return "pong"

# ---- QTick tools ----
@mcp.tool()
def appointments_book(
    business_id: str, customer_name: str, service_id: str, datetime: str
) -> Dict[str, Any]:
    """Book an appointment in QTick."""
    return _post("/tools/appointment/book", {
        "business_id": business_id,
        "customer_name": customer_name,
        "service_id": service_id,
        "datetime": datetime
    })

@mcp.tool()
def appointments_list(
    business_id: str,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> Dict[str, Any]:
    """List appointments for a business with optional filters and pagination."""
    return _post("/tools/appointment/list", {
        "business_id": business_id,
        "date_from": date_from,
        "date_to": date_to,
        "status": status,
        "page": page,
        "page_size": page_size
    })

@mcp.tool()
def invoice_create(
    business_id: str,
    customer_name: str,
    items: List[InvoiceItem],          # <-- typed list
    currency: str = "SGD",
    appointment_id: Optional[str] = None,
    notes: Optional[str] = None
) -> Dict[str, Any]:
    """Create an invoice with line items."""
    items_payload = [i.model_dump() for i in items]
    return _post("/tools/invoice/create", {
        "business_id": business_id,
        "customer_name": customer_name,
        "items": items_payload,
        "currency": currency,
        "appointment_id": appointment_id,
        "notes": notes
    })

@mcp.tool()
def leads_create(
    business_id: str,
    name: str,
    phone: Optional[str] = None,
    email: Optional[str] = None,
    source: str = "manual",
    notes: Optional[str] = None
) -> Dict[str, Any]:
    """Create a new customer lead."""
    return _post("/tools/leads/create", {
        "business_id": business_id,
        "name": name,
        "phone": phone,
        "email": email,
        "source": source,
        "notes": notes
    })

@mcp.tool()
def campaign_send_whatsapp(
    customer_name: str,
    phone_number: str,
    message_template: str,
    offer_code: Optional[str] = None,
    expiry: Optional[str] = None
) -> Dict[str, Any]:
    """Send a WhatsApp campaign message to a customer."""
    return _post("/tools/campaign/sendWhatsApp", {
        "customer_name": customer_name,
        "phone_number": phone_number,
        "message_template": message_template,
        "offer_code": offer_code,
        "expiry": expiry
    })

@mcp.tool()
def analytics_report(
    business_id: str,
    metrics: List[str],
    period: str
) -> Dict[str, Any]:
    """Fetch analytics for a business over a period."""
    return _post("/tools/analytics/report", {
        "business_id": business_id,
        "metrics": metrics,
        "period": period
    })
