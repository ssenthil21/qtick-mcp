# app/mcp_server.py
from __future__ import annotations

from typing import List, Optional, Literal
from pydantic import BaseModel, Field
from mcp.server.fastmcp import FastMCP, Context

# Name shown to clients (ChatGPT Custom Connector etc.)
mcp = FastMCP("qtick_mcp")

# --------------------------
# Shared, JSON-safe models
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
# Tools: inputs/outputs
# --------------------------
class AppointmentBookInput(BaseModel):
    business_id: str = Field(..., description="Business ID, e.g. 'chillbreeze'")
    customer_name: str = Field(..., description="Customer full name")
    service: str = Field(..., description="Service name, e.g. 'haircut'")
    start_time: str = Field(
        ..., description="Start time in ISO 8601, e.g. '2025-09-22T17:00:00+08:00'"
    )

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
    source: Optional[str] = Field(
        None, description="Lead source, e.g. 'walk-in', 'whatsapp', 'web'"
    )

class LeadCreateOutput(BaseModel):
    lead_id: str
    status: Literal["created"]

# --------------------------
# Tools: implementations
# --------------------------
@mcp.tool(name="appointments_book", description="Book an appointment")
async def appointments_book(input: AppointmentBookInput, ctx: Context) -> AppointmentBookOutput:
    # Simulate a successful booking (replace with real call to your Kotlin svc)
    appt_id = f"appt_{input.business_id}_{input.customer_name.replace(' ', '_')}"
    return AppointmentBookOutput(
        id=appt_id,
        business_id=input.business_id,
        customer_name=input.customer_name,
        service=input.service,
        start_time=input.start_time,
        status="booked",
    )

@mcp.tool(name="appointments_list", description="List appointments")
async def appointments_list(input: AppointmentListInput, ctx: Context) -> AppointmentListOutput:
    # Return an empty list as a safe default (replace with real data)
    return AppointmentListOutput(appointments=[])

@mcp.tool(name="invoice_create", description="Create an invoice from line items")
async def invoice_create(input: InvoiceCreateInput, ctx: Context) -> InvoiceCreateOutput:
    total = 0.0
    for it in input.items:
        total += float(it.quantity) * float(it.unit_price) * (1.0 + float(it.tax_rate))
    inv_id = f"inv_{input.business_id}"
    return InvoiceCreateOutput(invoice_id=inv_id, total=round(total, 2), currency=input.currency)

@mcp.tool(name="leads_create", description="Create a new lead for a business")
async def leads_create(input: LeadCreateInput, ctx: Context) -> LeadCreateOutput:
    lead_id = f"lead_{input.business_id}"
    return LeadCreateOutput(lead_id=lead_id, status="created")

@mcp.tool(name="ping", description="Health check")
async def ping(message: str) -> str:
    return f"pong: {message}"
