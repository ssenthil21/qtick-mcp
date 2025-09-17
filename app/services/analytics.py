from __future__ import annotations

import logging

from app.clients.java import JavaServiceClient
from app.schemas.analytics import AnalyticsRequest, AnalyticsResponse
from app.services.exceptions import ServiceError

logger = logging.getLogger(__name__)


class AnalyticsService:
    def __init__(self, client: JavaServiceClient) -> None:
        self._client = client

    async def generate_report(self, request: AnalyticsRequest) -> AnalyticsResponse:
        logger.debug("Generating analytics for business %s", request.business_id)
        if self._client.use_mock_data:
            await self._client.simulate_latency()
            return AnalyticsResponse(
                footfall=42,
                revenue="SGD 1,540",
                report_generated_at="2025-09-05T15:03:10+08:00",
            )

        try:
            payload = request.model_dump()
            data = await self._client.post("/analytics/report", payload)
            return AnalyticsResponse(**data)
        except ServiceError:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Unexpected error while generating analytics")
            raise ServiceError("Failed to generate analytics report", cause=exc)
