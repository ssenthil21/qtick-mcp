from __future__ import annotations

import logging

from app.clients.java import JavaServiceClient
from app.schemas.campaign import CampaignRequest, CampaignResponse
from app.services.exceptions import ServiceError
from app.services.mock_store import CampaignRepository, get_mock_store

logger = logging.getLogger(__name__)


class CampaignService:
    def __init__(
        self,
        client: JavaServiceClient,
        *,
        repository: CampaignRepository | None = None,
    ) -> None:
        self._client = client
        self._repository = repository
        if self._client.use_mock_data:
            self._repository = repository or get_mock_store().campaigns

    async def send_whatsapp(self, request: CampaignRequest) -> CampaignResponse:
        logger.debug("Sending WhatsApp campaign to %s", request.phone_number)
        if self._client.use_mock_data:
            await self._client.simulate_latency()
            if not self._repository:
                raise RuntimeError("Mock campaign repository not configured")
            return await self._repository.send_whatsapp(request)

        try:
            payload = request.model_dump()
            data = await self._client.post("/campaigns/whatsapp", payload)
            return CampaignResponse(**data)
        except ServiceError:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Unexpected error while sending campaign")
            raise ServiceError("Failed to send campaign", cause=exc)
