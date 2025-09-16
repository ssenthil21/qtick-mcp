
from fastapi import APIRouter
from app.schemas.billing import InvoiceRequest, InvoiceResponse
from datetime import datetime

router = APIRouter()

@router.post("/create", response_model=InvoiceResponse)
def create_invoice(req: InvoiceRequest):
    total = 0.0
    for item in req.items:
        # Support both 'unit_price' and alias 'price' at API layer (defensive)
        unit_price = getattr(item, "unit_price", None)
        if unit_price is None:
            unit_price = getattr(item, "price", None)
        if unit_price is None:
            unit_price = 0.0
        line = float(item.quantity) * float(unit_price)
        line = line * (1.0 + float(item.tax_rate))
        total += line
    total = round(total, 2)
    return InvoiceResponse(
        invoice_id="INV-10001",
        total=total,
        currency=req.currency,
        created_at=datetime.now().isoformat(),
        payment_link=f"https://pay.qtick.co/INV-10001",
        status="created"
    )
