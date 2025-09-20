from __future__ import annotations

import logging
from datetime import datetime

from app.clients.java import JavaServiceClient
from app.schemas.lead import LeadCreateRequest, LeadCreateResponse
from app.services.exceptions import ServiceError

logger = logging.getLogger(__name__)


class LeadService:
    def __init__(self, client: JavaServiceClient) -> None:
        self._client = client

    async def create(self, request: LeadCreateRequest) -> LeadCreateResponse:
        logger.info("Creating lead for %s", request.name)
        if self._client.use_mock_data:
            await self._client.simulate_latency()
            return LeadCreateResponse(
                lead_id="LEAD-90001",
                status="new",
                created_at=datetime.now().isoformat(),
            )

        try:
            payload = request.model_dump()
            data = await self._client.post("/leads", payload)
            return LeadCreateResponse(**data)
        except ServiceError:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Unexpected error while creating lead")
            raise ServiceError("Failed to create lead", cause=exc)
