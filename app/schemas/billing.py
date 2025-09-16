
from pydantic import BaseModel
from typing import List, Optional

class LineItem(BaseModel):
    item_id: Optional[str] = None
    description: str
    quantity: int
    unit_price: Optional[float] = None  # primary
    price: Optional[float] = None       # alias accepted by API/tool layer
    tax_rate: float = 0.0               # e.g. 0.08 for 8%

class InvoiceRequest(BaseModel):
    business_id: str
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
    payment_link: Optional[str] = None
    status: str
