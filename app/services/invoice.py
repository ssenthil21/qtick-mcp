from __future__ import annotations

import logging

from app.clients.java import JavaServiceClient
from app.schemas.billing import (
    InvoiceListRequest,
    InvoiceListResponse,
    InvoiceRequest,
    InvoiceResponse,
    InvoiceSummary,
)
from app.services.exceptions import ServiceError
from app.services.mock_store import InvoiceRepository, get_mock_store

logger = logging.getLogger(__name__)


class InvoiceService:
    def __init__(
        self,
        client: JavaServiceClient,
        *,
        repository: InvoiceRepository | None = None,
    ) -> None:
        self._client = client
        self._repository = repository
        if self._client.use_mock_data:
            self._repository = repository or get_mock_store().invoices

    async def create(self, request: InvoiceRequest) -> InvoiceResponse:
        logger.debug("Creating invoice for %s", request.customer_name)
        if self._client.use_mock_data:
            await self._client.simulate_latency()
            if not self._repository:
                raise RuntimeError("Mock invoice repository not configured")
            return await self._repository.create(request)

        try:
            payload = request.model_dump()
            data = await self._client.post("/invoices", payload)
            return InvoiceResponse(**data)
        except ServiceError:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Unexpected error while creating invoice")
            raise ServiceError("Failed to create invoice", cause=exc)

    async def list(self, request: InvoiceListRequest) -> InvoiceListResponse:
        logger.info("Listing invoices for business %s", request.business_id)
        if self._client.use_mock_data:
            await self._client.simulate_latency()
            if not self._repository:
                raise RuntimeError("Mock invoice repository not configured")
            invoices = await self._repository.list(request.business_id)
            items = [
                InvoiceSummary(
                    invoice_id=invoice["invoice_id"],
                    total=float(invoice["total"]),
                    currency=str(invoice["currency"]),
                    created_at=str(invoice["created_at"]),
                    status=str(invoice["status"]),
                )
                for invoice in invoices
            ]
            return InvoiceListResponse(total=len(items), items=items)

        try:
            payload = request.model_dump()
            data = await self._client.post("/invoices/list", payload)
            return InvoiceListResponse(**data)
        except ServiceError:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Unexpected error while listing invoices")
            raise ServiceError("Failed to list invoices", cause=exc)
