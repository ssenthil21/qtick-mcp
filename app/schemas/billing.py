
from typing import List, Optional

from pydantic import BaseModel

class LineItem(BaseModel):
    item_id: Optional[str] = None
    description: str
    quantity: int
    unit_price: Optional[float] = None  # primary
    price: Optional[float] = None       # alias accepted by API/tool layer
    tax_rate: float = 0.0               # e.g. 0.08 for 8%

class InvoiceRequest(BaseModel):
    business_id: int
    customer_name: str
    items: List[LineItem]
    currency: str = "SGD"
    appointment_id: Optional[str] = None
    notes: Optional[str] = None

class InvoiceResponse(BaseModel):
    invoice_id: str
    total: float
    currency: str
    created_at: str
    customer_name: Optional[str] = None
    payment_link: Optional[str] = None
    status: str
    paid_at: Optional[str] = None
    review_request_id: Optional[str] = None


class InvoiceSummary(BaseModel):
    invoice_id: str
    total: float
    currency: str
    created_at: str
    status: str
    customer_name: Optional[str] = None
    paid_at: Optional[str] = None


class InvoiceListRequest(BaseModel):
    business_id: int


class InvoiceListResponse(BaseModel):
    total: int
    items: List[InvoiceSummary]


class InvoicePaymentRequest(BaseModel):
    invoice_id: str
    paid_at: Optional[str] = None
