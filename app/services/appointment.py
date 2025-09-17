from __future__ import annotations

import logging
from typing import List

from app.clients.java import JavaServiceClient
from app.schemas.appointment import (
    AppointmentListRequest,
    AppointmentListResponse,
    AppointmentRequest,
    AppointmentResponse,
    AppointmentSummary,
)
from app.services.exceptions import ServiceError

logger = logging.getLogger(__name__)


class AppointmentService:
    def __init__(self, client: JavaServiceClient) -> None:
        self._client = client

    async def book(self, request: AppointmentRequest) -> AppointmentResponse:
        logger.debug("Booking appointment for %s", request.customer_name)
        if self._client.use_mock_data:
            await self._client.simulate_latency()
            return AppointmentResponse(
                status="confirmed",
                appointment_id="APT-33451",
                queue_number="B17",
            )

        try:
            payload = request.model_dump()
            data = await self._client.post("/appointments/book", payload)
            return AppointmentResponse(**data)
        except ServiceError:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Unexpected error while booking appointment")
            raise ServiceError("Failed to book appointment", cause=exc)

    async def list(self, request: AppointmentListRequest) -> AppointmentListResponse:
        logger.debug("Listing appointments for business %s", request.business_id)
        if self._client.use_mock_data:
            await self._client.simulate_latency()
            items: List[AppointmentSummary] = [
                AppointmentSummary(
                    appointment_id="APT-33451",
                    customer_name="Alex",
                    service_id="haircut",
                    datetime="2025-09-06T17:00:00+08:00",
                    status="confirmed",
                    queue_number="B17",
                ),
                AppointmentSummary(
                    appointment_id="APT-33452",
                    customer_name="Jane",
                    service_id="facial",
                    datetime="2025-09-06T18:30:00+08:00",
                    status="pending",
                    queue_number=None,
                ),
            ]
            start = (request.page - 1) * request.page_size
            end = start + request.page_size
            return AppointmentListResponse(
                total=len(items),
                page=request.page,
                page_size=request.page_size,
                items=items[start:end],
            )

        try:
            payload = request.model_dump()
            data = await self._client.post("/appointments/list", payload)
            return AppointmentListResponse(**data)
        except ServiceError:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Unexpected error while listing appointments")
            raise ServiceError("Failed to list appointments", cause=exc)
