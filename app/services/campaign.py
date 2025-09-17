from __future__ import annotations

import logging

from app.clients.java import JavaServiceClient
from app.schemas.campaign import CampaignRequest, CampaignResponse
from app.services.exceptions import ServiceError

logger = logging.getLogger(__name__)


class CampaignService:
    def __init__(self, client: JavaServiceClient) -> None:
        self._client = client

    async def send_whatsapp(self, request: CampaignRequest) -> CampaignResponse:
        logger.debug("Sending WhatsApp campaign to %s", request.phone_number)
        if self._client.use_mock_data:
            await self._client.simulate_latency()
            return CampaignResponse(
                status="sent",
                delivery_time="2025-09-05T15:02:03+08:00",
            )

        try:
            payload = request.model_dump()
            data = await self._client.post("/campaigns/whatsapp", payload)
            return CampaignResponse(**data)
        except ServiceError:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Unexpected error while sending campaign")
            raise ServiceError("Failed to send campaign", cause=exc)
