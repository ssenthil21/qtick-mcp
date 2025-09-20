from __future__ import annotations

import logging

from app.clients.java import JavaServiceClient
from app.schemas.lead import LeadCreateRequest, LeadCreateResponse
from app.services.exceptions import ServiceError
from app.services.mock_store import LeadRepository, get_mock_store

logger = logging.getLogger(__name__)


class LeadService:
    def __init__(
        self,
        client: JavaServiceClient,
        *,
        repository: LeadRepository | None = None,
    ) -> None:
        self._client = client
        self._repository = repository
        if self._client.use_mock_data:
            self._repository = repository or get_mock_store().leads

    async def create(self, request: LeadCreateRequest) -> LeadCreateResponse:
        logger.info("Creating lead for %s", request.name)
        if self._client.use_mock_data:
            await self._client.simulate_latency()
            if not self._repository:
                raise RuntimeError("Mock lead repository not configured")
            return await self._repository.create(request)

        try:
            payload = request.model_dump()
            data = await self._client.post("/leads", payload)
            return LeadCreateResponse(**data)
        except ServiceError:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Unexpected error while creating lead")
            raise ServiceError("Failed to create lead", cause=exc)
