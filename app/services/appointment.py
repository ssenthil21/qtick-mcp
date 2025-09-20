from __future__ import annotations

import logging

from app.clients.java import JavaServiceClient
from app.schemas.appointment import (
    AppointmentListRequest,
    AppointmentListResponse,
    AppointmentRequest,
    AppointmentResponse,
)
from app.services.exceptions import ServiceError
from app.services.mock_store import AppointmentRepository, get_mock_store

logger = logging.getLogger(__name__)


class AppointmentService:
    def __init__(
        self,
        client: JavaServiceClient,
        *,
        repository: AppointmentRepository | None = None,
    ) -> None:
        self._client = client
        self._repository = repository
        if self._client.use_mock_data:
            self._repository = repository or get_mock_store().appointments

    async def book(self, request: AppointmentRequest) -> AppointmentResponse:
        logger.info("Booking appointment for %s", request.customer_name)
        if self._client.use_mock_data:
            await self._client.simulate_latency()
            if not self._repository:
                raise RuntimeError("Mock appointment repository not configured")
            return await self._repository.book(request)

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
        logger.info("Listing appointments for business %s", request.business_id)
        if self._client.use_mock_data:
            await self._client.simulate_latency()
            if not self._repository:
                raise RuntimeError("Mock appointment repository not configured")
            return await self._repository.list(request)

        try:
            payload = request.model_dump()
            data = await self._client.post("/appointments/list", payload)
            return AppointmentListResponse(**data)
        except ServiceError:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Unexpected error while listing appointments")
            raise ServiceError("Failed to list appointments", cause=exc)
