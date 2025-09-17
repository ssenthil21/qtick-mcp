from __future__ import annotations

import logging
from datetime import datetime

from app.clients.java import JavaServiceClient
from app.schemas.billing import InvoiceRequest, InvoiceResponse
from app.services.exceptions import ServiceError

logger = logging.getLogger(__name__)


class InvoiceService:
    def __init__(self, client: JavaServiceClient) -> None:
        self._client = client

    async def create(self, request: InvoiceRequest) -> InvoiceResponse:
        logger.debug("Creating invoice for %s", request.customer_name)
        if self._client.use_mock_data:
            await self._client.simulate_latency()
            total = 0.0
            for item in request.items:
                unit_price = getattr(item, "unit_price", None)
                if unit_price is None:
                    unit_price = getattr(item, "price", None)
                if unit_price is None:
                    unit_price = 0.0
                line_total = float(item.quantity) * float(unit_price)
                line_total *= 1.0 + float(item.tax_rate)
                total += line_total
            total = round(total, 2)
            invoice_id = "INV-10001"
            return InvoiceResponse(
                invoice_id=invoice_id,
                total=total,
                currency=request.currency,
                created_at=datetime.now().isoformat(),
                payment_link=f"https://pay.qtick.co/{invoice_id}",
                status="created",
            )

        try:
            payload = request.model_dump()
            data = await self._client.post("/invoices", payload)
            return InvoiceResponse(**data)
        except ServiceError:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Unexpected error while creating invoice")
            raise ServiceError("Failed to create invoice", cause=exc)
