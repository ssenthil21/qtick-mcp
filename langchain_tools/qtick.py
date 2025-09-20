
import os
from datetime import datetime, timedelta
import re
from typing import List, Optional

import dateparser
import requests
from langchain.tools import StructuredTool
from pydantic import BaseModel, Field, validator
from zoneinfo import ZoneInfo

from app.config import runtime_default_mcp_base_url


def _resolve_mcp_base_url() -> str:
    """Return the MCP base URL honouring explicit overrides when present."""

    base = os.getenv("QTICK_MCP_BASE_URL")
    if base:
        return base.rstrip("/")
    return runtime_default_mcp_base_url()


MCP_BASE = _resolve_mcp_base_url()


def configure(*, base_url: Optional[str] = None) -> None:
    """Configure the MCP base URL used by the LangChain tools."""

    global MCP_BASE
    if base_url:
        MCP_BASE = base_url.rstrip("/")

# ---------- Appointment Book ----------
class BookAppointmentInput(BaseModel):
    business_id: str
    customer_name: str
    service_id: str
    datetime: str

    @validator("datetime")
    def ensure_iso8601(cls, v):
        try:
            datetime.fromisoformat(v.replace("Z", "+00:00"))
        except Exception:
            raise ValueError("datetime must be ISO 8601 (e.g. 2025-09-06T17:00:00+08:00)")
        return v

def _book_appointment(business_id: str, customer_name: str, service_id: str, datetime: str):
    payload = {"business_id": business_id, "customer_name": customer_name, "service_id": service_id, "datetime": datetime}
    r = requests.post(f"{MCP_BASE}/tools/appointment/book", json=payload, timeout=15)
    r.raise_for_status()
    return r.json()

def appointment_tool():
    return StructuredTool.from_function(
        name="appointment_book",
        description="Book a QTick appointment (ISO 8601 datetime required).",
        func=_book_appointment,
        args_schema=BookAppointmentInput,
    )

# ---------- Appointment List ----------
class AppointmentListInput(BaseModel):
    business_id: str
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    status: Optional[str] = None
    page: int = 1
    page_size: int = 20

def _list_appointments(business_id: str, date_from: Optional[str] = None, date_to: Optional[str] = None, status: Optional[str] = None, page: int = 1, page_size: int = 20):
    payload = {"business_id": business_id, "date_from": date_from, "date_to": date_to, "status": status, "page": page, "page_size": page_size}
    r = requests.post(f"{MCP_BASE}/tools/appointment/list", json=payload, timeout=15)
    r.raise_for_status()
    return r.json()

def appointment_list_tool():
    return StructuredTool.from_function(
        name="appointment_list",
        description="List appointments for a business with optional filters (date range, status, pagination).",
        func=_list_appointments,
        args_schema=AppointmentListInput,
    )

# ---------- Invoice Create ----------
class LineItemInput(BaseModel):
    item_id: Optional[str] = None
    description: str
    quantity: int
    # accept unit_price or alias price
    unit_price: Optional[float] = None
    price: Optional[float] = None
    tax_rate: float = 0.0

    @validator("unit_price", always=True)
    def coerce_unit_price(cls, v, values):
        if v is None:
            alt = values.get("price")
            if alt is None:
                raise ValueError("unit_price (or alias 'price') is required")
            return alt
        return v

class InvoiceCreateInput(BaseModel):
    business_id: str
    customer_name: str
    items: List[LineItemInput]
    currency: str = "SGD"
    appointment_id: Optional[str] = None
    notes: Optional[str] = None

def _invoice_create(business_id: str, customer_name: str, items: List[LineItemInput], currency: str = "SGD", appointment_id: Optional[str] = None, notes: Optional[str] = None):
    norm_items = []
    for i in items:
        norm_items.append({
            "item_id": i.item_id,
            "description": i.description,
            "quantity": i.quantity,
            "unit_price": i.unit_price if i.unit_price is not None else i.price,
            "tax_rate": i.tax_rate
        })
    payload = {"business_id": business_id, "customer_name": customer_name, "items": norm_items, "currency": currency, "appointment_id": appointment_id, "notes": notes}
    r = requests.post(f"{MCP_BASE}/tools/invoice/create", json=payload, timeout=15)
    r.raise_for_status()
    return r.json()

def invoice_create_tool():
    return StructuredTool.from_function(
        name="invoice_create",
        description="Create an invoice with line items. Accepts 'unit_price' or 'price'. Returns invoice id, total, and payment link.",
        func=_invoice_create,
        args_schema=InvoiceCreateInput,
    )

# ---------- Lead Create ----------
class LeadCreateInput(BaseModel):
    business_id: str
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    source: Optional[str] = "manual"
    notes: Optional[str] = None

def _lead_create(business_id: str, name: str, phone: Optional[str] = None, email: Optional[str] = None, source: Optional[str] = "manual", notes: Optional[str] = None):
    payload = {"business_id": business_id, "name": name, "phone": phone, "email": email, "source": source, "notes": notes}
    r = requests.post(f"{MCP_BASE}/tools/leads/create", json=payload, timeout=15)
    r.raise_for_status()
    return r.json()

def lead_create_tool():
    return StructuredTool.from_function(
        name="lead_create",
        description="Create a new customer lead with optional contact details and source.",
        func=_lead_create,
        args_schema=LeadCreateInput,
    )

# ---------- Campaign WhatsApp ----------
class SendWhatsAppInput(BaseModel):
    customer_name: str
    phone_number: str
    message_template: str
    offer_code: str
    expiry: str

def _send_whatsapp(customer_name: str, phone_number: str, message_template: str, offer_code: str, expiry: str):
    payload = {"customer_name": customer_name, "phone_number": phone_number, "message_template": message_template, "offer_code": offer_code, "expiry": expiry}
    r = requests.post(f"{MCP_BASE}/tools/campaign/sendWhatsApp", json=payload, timeout=15)
    r.raise_for_status()
    return r.json()

def campaign_tool():
    return StructuredTool.from_function(
        name="campaign_send_whatsapp",
        description="Send a WhatsApp promo/notification to a customer.",
        func=_send_whatsapp,
        args_schema=SendWhatsAppInput,
    )

# ---------- Analytics ----------
class AnalyticsInput(BaseModel):
    business_id: str
    metrics: List[str] = Field(..., description="e.g. ['footfall','revenue']")
    period: str

def _analytics_report(business_id: str, metrics: List[str], period: str):
    payload = {"business_id": business_id, "metrics": metrics, "period": period}
    r = requests.post(f"{MCP_BASE}/tools/analytics/report", json=payload, timeout=15)
    r.raise_for_status()
    return r.json()

def analytics_tool():
    return StructuredTool.from_function(
        name="analytics_report",
        description="Fetch analytics for a business for a period.",
        func=_analytics_report,
        args_schema=AnalyticsInput,
    )

# ---------- DateTime Parser ----------
class DateTimeParseInput(BaseModel):
    text: str = Field(..., description="Natural datetime e.g. 'tomorrow 5 PM Singapore'")

def _parse_datetime(text: str):
    tz = ZoneInfo("Asia/Singapore")
    now = datetime.now(tz)
    t = text.strip()
    t = re.sub(r"\b(singapore|sg|sgt)\b", "", t, flags=re.I).strip()

    dp = dateparser.parse(
        t,
        settings={
            "TIMEZONE": "Asia/Singapore",
            "TO_TIMEZONE": "Asia/Singapore",
            "RETURN_AS_TIMEZONE_AWARE": True,
            "PREFER_DATES_FROM": "future",
            "RELATIVE_BASE": now,
            "DATE_ORDER": "DMY",
        },
        languages=["en"],
    )
    if dp:
        if dp.tzinfo is None:
            dp = dp.replace(tzinfo=tz)
        else:
            dp = dp.astimezone(tz)
        return {"iso8601": dp.isoformat()}

    low = t.lower()
    if "tomorrow" in low:
        m = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", low, re.I)
        if m:
            hour = int(m.group(1))
            minute = int(m.group(2)) if m.group(2) else 0
            ampm = m.group(3).lower() if m.group(3) else None
            if ampm == "pm" and hour < 12:
                hour += 12
            if ampm == "am" and hour == 12:
                hour = 0
            dt = (now + timedelta(days=1)).replace(hour=hour, minute=minute, second=0, microsecond=0)
            return {"iso8601": dt.isoformat()}

    m2 = re.search(r"(\d{4}-\d{2}-\d{2})\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", t, re.I)
    if m2:
        date_str = m2.group(1)
        hour = int(m2.group(2))
        minute = int(m2.group(3)) if m2.group(3) else 0
        ampm = m2.group(4).lower() if m2.group(4) else None
        if ampm == "pm" and hour < 12:
            hour += 12
        if ampm == "am" and hour == 12:
            hour = 0
        y, mo, d = [int(x) for x in date_str.split("-")]
        dt = datetime(y, mo, d, hour, minute, tzinfo=tz)
        return {"iso8601": dt.isoformat()}

    return {"error": f"Could not parse datetime from: {text}"}

def datetime_tool():
    return StructuredTool.from_function(
        name="datetime_parse",
        description="Convert natural language datetime into ISO 8601 format string. Assumes Asia/Singapore timezone unless otherwise specified.",
        func=_parse_datetime,
        args_schema=DateTimeParseInput,
    )

__all__ = [
    "appointment_tool",
    "appointment_list_tool",
    "invoice_create_tool",
    "lead_create_tool",
    "campaign_tool",
    "analytics_tool",
    "datetime_tool",
    "configure",
]
