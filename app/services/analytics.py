from __future__ import annotations

import logging

from app.clients.java import JavaServiceClient
from app.schemas.analytics import AnalyticsRequest, AnalyticsResponse
from app.services.exceptions import ServiceError
from app.services.mock_store import AnalyticsRepository, get_mock_store

logger = logging.getLogger(__name__)


class AnalyticsService:
    def __init__(
        self,
        client: JavaServiceClient,
        *,
        repository: AnalyticsRepository | None = None,
    ) -> None:
        self._client = client
        self._repository = repository
        if self._client.use_mock_data:
            self._repository = repository or get_mock_store().analytics

    async def generate_report(self, request: AnalyticsRequest) -> AnalyticsResponse:
        logger.debug("Generating analytics for business %s", request.business_id)
        if self._client.use_mock_data:
            await self._client.simulate_latency()
            if not self._repository:
                raise RuntimeError("Mock analytics repository not configured")
            return await self._repository.generate_report(request)

        try:
            payload = request.model_dump()
            data = await self._client.post("/analytics/report", payload)
            return AnalyticsResponse(**data)
        except ServiceError:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Unexpected error while generating analytics")
            raise ServiceError("Failed to generate analytics report", cause=exc)
