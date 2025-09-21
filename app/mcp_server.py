# app/mcp_server.py (DEBUG-safe schemas)
from __future__ import annotations

import logging
from typing import List, Optional, Literal
from pydantic import BaseModel, Field
from mcp.server.fastmcp import FastMCP, Context

log = logging.getLogger("qtick.mcp")

# Name shown to clients (ChatGPT Custom Connector etc.)
mcp = FastMCP("qtick_mcp")

# --------------------------
# JSON-safe models
# --------------------------
class Appointment(BaseModel):
    id: str
    business_id: str
    customer_name: str
    service: str
    start_time: str  # ISO 8601 string
    status: Literal["booked", "completed", "cancelled"] = "booked"

class InvoiceItem(BaseModel):
    description: str
    quantity: int
    unit_price: float
    tax_rate: float = 0.0

# --------------------------
# Tool I/O models
# --------------------------
class AppointmentBookInput(BaseModel):
    business_id: str = Field(..., description="Business ID, e.g. 'chillbreeze'")
    customer_name: str = Field(..., description="Customer full name")
    service: str = Field(..., description="Service name, e.g. 'haircut'")
    start_time: str = Field(..., description="Start time ISO 8601, e.g. '2025-09-22T17:00:00+08:00'")

class AppointmentBookOutput(Appointment):
    pass

class AppointmentListInput(BaseModel):
    business_id: str
    date_from: Optional[str] = Field(None, description="ISO date/time start (inclusive)")
    date_to: Optional[str] = Field(None, description="ISO date/time end (inclusive)")
    status: Optional[Literal["booked", "completed", "cancelled"]] = None

class AppointmentListOutput(BaseModel):
    appointments: List[Appointment]

class InvoiceCreateInput(BaseModel):
    business_id: str
    customer_name: str
    currency: str = "SGD"
    items: List[InvoiceItem]

class InvoiceCreateOutput(BaseModel):
    invoice_id: str
    total: float
    currency: str

class LeadCreateInput(BaseModel):
    business_id: str
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    source: Optional[str] = Field(None, description="Lead source, e.g. 'walk-in', 'whatsapp', 'web'")

class LeadCreateOutput(BaseModel):
    lead_id: str
    status: Literal["created"]

# --------------------------
# Tools
# --------------------------
@mcp.tool(name="appointments_book", description="Book an appointment")
async def appointments_book(input: AppointmentBookInput, ctx: Context) -> AppointmentBookOutput:
    log.debug("appointments_book input=%s", input.model_dump())
    appt_id = f"appt_{input.business_id}_{input.customer_name.replace(' ', '_')}"
    out = AppointmentBookOutput(
        id=appt_id,
        business_id=input.business_id,
        customer_name=input.customer_name,
        service=input.service,
        start_time=input.start_time,
        status="booked",
    )
    log.debug("appointments_book output=%s", out.model_dump())
    return out

@mcp.tool(name="appointments_list", description="List appointments")
async def appointments_list(input: AppointmentListInput, ctx: Context) -> AppointmentListOutput:
    log.debug("appointments_list input=%s", input.model_dump())
    out = AppointmentListOutput(appointments=[])
    log.debug("appointments_list output=%s", out.model_dump())
    return out

@mcp.tool(name="invoice_create", description="Create an invoice from line items")
async def invoice_create(input: InvoiceCreateInput, ctx: Context) -> InvoiceCreateOutput:
    log.debug("invoice_create input=%s", input.model_dump())
    total = 0.0
    for it in input.items:
        total += float(it.quantity) * float(it.unit_price) * (1.0 + float(it.tax_rate))
    out = InvoiceCreateOutput(
        invoice_id=f"inv_{input.business_id}",
        total=round(total, 2),
        currency=input.currency,
    )
    log.debug("invoice_create output=%s", out.model_dump())
    return out

@mcp.tool(name="leads_create", description="Create a new lead for a business")
async def leads_create(input: LeadCreateInput, ctx: Context) -> LeadCreateOutput:
    log.debug("leads_create input=%s", input.model_dump())
    out = LeadCreateOutput(lead_id=f"lead_{input.business_id}", status="created")
    log.debug("leads_create output=%s", out.model_dump())
    return out

@mcp.tool(name="ping", description="Health check")
async def ping(message: str) -> str:
    log.debug("ping %s", message)
    return f"pong: {message}"
