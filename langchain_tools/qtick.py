
import os
import re
from datetime import datetime, timedelta
from typing import List, Optional

import dateparser
import requests
from zoneinfo import ZoneInfo
from langchain.tools import StructuredTool
from pydantic import BaseModel, Field, field_validator, model_validator

from app.config import runtime_default_mcp_base_url


def _resolve_mcp_base_url() -> str:
    """Return the MCP base URL honouring explicit overrides when present."""

    base = os.getenv("QTICK_MCP_BASE_URL")
    if base:
        return base.rstrip("/")
    return runtime_default_mcp_base_url()


def _resolve_request_timeout() -> float:
    """Resolve the timeout to use for tool HTTP requests."""

    for env_key in ("QTICK_AGENT_TOOL_TIMEOUT", "AGENT_TOOL_TIMEOUT"):
        raw = os.getenv(env_key)
        if not raw:
            continue
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        if value > 0:
            return value
    return 30.0


def _normalize_timeout(value: float) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
        raise ValueError("timeout must be a positive number") from exc
    if numeric <= 0:  # pragma: no cover - defensive
        raise ValueError("timeout must be positive")
    return numeric


MCP_BASE = _resolve_mcp_base_url()
REQUEST_TIMEOUT = _resolve_request_timeout()


def configure(*, base_url: Optional[str] = None, timeout: Optional[float] = None) -> None:
    """Configure the MCP base URL used by the LangChain tools."""

    global MCP_BASE, REQUEST_TIMEOUT
    if base_url:
        MCP_BASE = base_url.rstrip("/")
    if timeout is not None:
        REQUEST_TIMEOUT = _normalize_timeout(timeout)


def _post_tool(path: str, payload: dict) -> dict:
    response = requests.post(
        f"{MCP_BASE}{path}", json=payload, timeout=REQUEST_TIMEOUT
    )
    response.raise_for_status()
    return response.json()

# ---------- Business Search ----------
class BusinessSearchInput(BaseModel):
    query: str
    limit: int = Field(default=10, ge=1, le=25)


def _business_search(query: str, limit: int = 10):
    payload = {"query": query, "limit": limit}
    return _post_tool("/tools/business/search", payload)


def business_search_tool():
    return StructuredTool.from_function(
        name="business_search",
        description="Search for QTick businesses by name, id, or tags.",
        func=_business_search,
        args_schema=BusinessSearchInput,
    )


# ---------- Service Lookup ----------
class ServiceLookupInput(BaseModel):
    service_name: str = Field(..., description="Service name or keyword")
    business_id: Optional[int] = None
    business_name: Optional[str] = None
    limit: int = Field(default=5, ge=1, le=20)


def _service_lookup(
    service_name: str,
    business_id: Optional[int] = None,
    business_name: Optional[str] = None,
    limit: int = 5,
):
    payload = {
        "service_name": service_name,
        "business_id": business_id,
        "business_name": business_name,
        "limit": limit,
    }
    return _post_tool("/tools/business/services/find", payload)


def business_service_lookup_tool():
    return StructuredTool.from_function(
        name="business_service_lookup",
        description="Find service identifiers for a business using keywords.",
        func=_service_lookup,
        args_schema=ServiceLookupInput,
    )


# ---------- Appointment Book ----------
class BookAppointmentInput(BaseModel):
    business_id: int
    customer_name: str
    service_id: int
    datetime: str

    @field_validator("datetime")
    def ensure_iso8601(cls, value: str) -> str:
        try:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
        except Exception as exc:  # pragma: no cover - defensive
            raise ValueError(
                "datetime must be ISO 8601 (e.g. 2025-09-06T17:00:00+08:00)"
            ) from exc
        return value

def _book_appointment(business_id: int, customer_name: str, service_id: int, datetime: str):
    payload = {"business_id": business_id, "customer_name": customer_name, "service_id": service_id, "datetime": datetime}
    return _post_tool("/tools/appointment/book", payload)

def appointment_tool():
    return StructuredTool.from_function(
        name="appointment_book",
        description="Book a QTick appointment (ISO 8601 datetime required).",
        func=_book_appointment,
        args_schema=BookAppointmentInput,
    )

# ---------- Appointment List ----------
class AppointmentListInput(BaseModel):
    business_id: int
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    status: Optional[str] = None
    page: int = 1
    page_size: int = 20

def _list_appointments(business_id: int, date_from: Optional[str] = None, date_to: Optional[str] = None, status: Optional[str] = None, page: int = 1, page_size: int = 20):
    payload = {"business_id": business_id, "date_from": date_from, "date_to": date_to, "status": status, "page": page, "page_size": page_size}
    return _post_tool("/tools/appointment/list", payload)

def appointment_list_tool():
    return StructuredTool.from_function(
        name="appointment_list",
        description="List appointments for a business with optional filters (date range, status, pagination).",
        func=_list_appointments,
        args_schema=AppointmentListInput,
    )

# ---------- Invoice List ----------
class InvoiceListInput(BaseModel):
    business_id: int


def _invoice_list(business_id: int):
    payload = {"business_id": business_id}
    return _post_tool("/tools/invoice/list", payload)


def invoice_list_tool():
    return StructuredTool.from_function(
        name="invoice_list",
        description="List invoices raised for a business.",
        func=_invoice_list,
        args_schema=InvoiceListInput,
    )

# ---------- Invoice Mark Paid ----------
class InvoiceMarkPaidInput(BaseModel):
    invoice_id: str
    paid_at: Optional[str] = None

    @field_validator("paid_at")
    def ensure_paid_at(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        try:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
        except Exception as exc:  # pragma: no cover - defensive
            raise ValueError("paid_at must be ISO 8601") from exc
        return value


def _invoice_mark_paid(invoice_id: str, paid_at: Optional[str] = None):
    payload = {"invoice_id": invoice_id, "paid_at": paid_at}
    return _post_tool("/tools/invoice/mark-paid", payload)


def invoice_mark_paid_tool():
    return StructuredTool.from_function(
        name="invoice_mark_paid",
        description="Mark an invoice as paid and trigger the post-payment review flow.",
        func=_invoice_mark_paid,
        args_schema=InvoiceMarkPaidInput,
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
    service_id: Optional[int] = None

    @model_validator(mode="after")
    def ensure_unit_price(cls, model: "LineItemInput") -> "LineItemInput":
        if model.unit_price is None:
            if model.price is None:
                raise ValueError("unit_price (or alias 'price') is required")
            model.unit_price = model.price
        return model

class InvoiceCreateInput(BaseModel):
    business_id: int
    customer_name: str
    items: List[LineItemInput]
    currency: str = "SGD"
    appointment_id: Optional[str] = None
    notes: Optional[str] = None

def _invoice_create(business_id: int, customer_name: str, items: List[LineItemInput], currency: str = "SGD", appointment_id: Optional[str] = None, notes: Optional[str] = None):
    norm_items = []
    for i in items:
        normalized = {
            "item_id": i.item_id,
            "description": i.description,
            "quantity": i.quantity,
            "unit_price": i.unit_price if i.unit_price is not None else i.price,
            "tax_rate": i.tax_rate
        }
        if i.service_id is not None:
            normalized["service_id"] = i.service_id
        norm_items.append(normalized)
    payload = {"business_id": business_id, "customer_name": customer_name, "items": norm_items, "currency": currency, "appointment_id": appointment_id, "notes": notes}
    return _post_tool("/tools/invoice/create", payload)

def invoice_create_tool():
    return StructuredTool.from_function(
        name="invoice_create",
        description="Create an invoice with line items. Accepts 'unit_price' or 'price'. Returns invoice id, total, and payment link.",
        func=_invoice_create,
        args_schema=InvoiceCreateInput,
    )

# ---------- Lead Create ----------
class LeadCreateInput(BaseModel):
    business_id: int
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    source: Optional[str] = "manual"
    notes: Optional[str] = None

def _lead_create(
    business_id: int,
    name: str,
    phone: Optional[str] = None,
    email: Optional[str] = None,
    source: Optional[str] = "manual",
    notes: Optional[str] = None,
):
    payload = {"business_id": business_id, "name": name, "phone": phone, "email": email, "source": source, "notes": notes}
    return _post_tool("/tools/leads/create", payload)

def lead_create_tool():
    return StructuredTool.from_function(
        name="lead_create",
        description="Create a new customer lead with optional contact details and source.",
        func=_lead_create,
        args_schema=LeadCreateInput,
    )

# ---------- Lead List ----------
class LeadListInput(BaseModel):
    business_id: int


def _lead_list(business_id: int):
    payload = {"business_id": business_id}
    return _post_tool("/tools/leads/list", payload)


def lead_list_tool():
    return StructuredTool.from_function(
        name="lead_list",
        description="List captured leads for a business.",
        func=_lead_list,
        args_schema=LeadListInput,
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
    return _post_tool("/tools/campaign/sendWhatsApp", payload)

def campaign_tool():
    return StructuredTool.from_function(
        name="campaign_send_whatsapp",
        description="Send a WhatsApp promo/notification to a customer.",
        func=_send_whatsapp,
        args_schema=SendWhatsAppInput,
    )

# ---------- Analytics ----------
class AnalyticsInput(BaseModel):
    business_id: int
    metrics: List[str] = Field(..., description="e.g. ['footfall','revenue']")
    period: str

def _analytics_report(business_id: int, metrics: List[str], period: str):
    payload = {"business_id": business_id, "metrics": metrics, "period": period}
    return _post_tool("/tools/analytics/report", payload)

def analytics_tool():
    return StructuredTool.from_function(
        name="analytics_report",
        description=(
            "Fetch analytics for a business including appointment, invoice, and "
            "lead breakdowns for a period."
        ),
        func=_analytics_report,
        args_schema=AnalyticsInput,
    )


# ---------- Daily Summary ----------
class DailySummaryInput(BaseModel):
    business_id: int
    date: Optional[str] = Field(
        default=None, description="ISO formatted date (YYYY-MM-DD). Defaults to today."
    )
    metrics: Optional[List[str]] = Field(
        default=None,
        description="Optional list of metric identifiers forwarded to analytics backend.",
    )
    period: str = Field(
        default="day",
        description="Reporting period hint understood by the analytics service.",
    )

    @field_validator("date")
    @classmethod
    def ensure_date(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        try:
            datetime.fromisoformat(value)
        except Exception as exc:  # pragma: no cover - defensive
            raise ValueError("date must be provided in ISO format YYYY-MM-DD") from exc
        return value


def _daily_summary(
    business_id: int,
    date: Optional[str] = None,
    metrics: Optional[List[str]] = None,
    period: str = "day",
):
    payload = {
        "business_id": business_id,
        "date": date,
        "metrics": metrics,
        "period": period,
    }
    return _post_tool("/tools/business/daily-summary", payload)


def daily_summary_tool():
    return StructuredTool.from_function(
        name="daily_summary",
        description="Generate an LLM-authored daily business summary with key metrics.",
        func=_daily_summary,
        args_schema=DailySummaryInput,
    )


# ---------- Live Operations Summary ----------
class LiveOpsInput(BaseModel):
    business_id: int
    date: Optional[str] = None

    @field_validator("date")
    def ensure_date(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        try:
            datetime.fromisoformat(value)
        except Exception as exc:  # pragma: no cover - defensive
            raise ValueError("date must be YYYY-MM-DD") from exc
        return value


def _live_ops_events(business_id: int, date: Optional[str] = None):
    payload = {"business_id": business_id, "date": date}
    return _post_tool("/tools/live-ops/events", payload)


def live_ops_tool():
    return StructuredTool.from_function(
        name="live_ops_events",
        description="Summarise key business events (appointments, invoices, leads, reviews) for today.",
        func=_live_ops_events,
        args_schema=LiveOpsInput,
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
    "daily_summary_tool",
    "datetime_tool",
    "configure",
]
