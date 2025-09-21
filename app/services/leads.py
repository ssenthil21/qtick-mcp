from __future__ import annotations

import logging

from app.clients.java import JavaServiceClient
from app.schemas.lead import (
    LeadCreateRequest,
    LeadCreateResponse,
    LeadListRequest,
    LeadListResponse,
    LeadSummary,
)
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
            response = await self._repository.create(request)
            return LeadCreateResponse(
                lead_id=response.lead_id,
                status=response.status,
                created_at=response.created_at,
                next_action="Schedule a follow-up call or message with this lead within 24 hours.",
                follow_up_required=True,
            )

        try:
            payload = request.model_dump()
            data = await self._client.post("/leads", payload)
            return LeadCreateResponse(
                **data,
                next_action=data.get(
                    "next_action",
                    "Schedule a follow-up call or message with this lead within 24 hours.",
                ),
                follow_up_required=data.get("follow_up_required", True),
            )
        except ServiceError:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Unexpected error while creating lead")
            raise ServiceError("Failed to create lead", cause=exc)

    async def list(self, request: LeadListRequest) -> LeadListResponse:
        logger.info("Listing leads for business %s", request.business_id)
        if self._client.use_mock_data:
            await self._client.simulate_latency()
            if not self._repository:
                raise RuntimeError("Mock lead repository not configured")
            leads = await self._repository.list(request.business_id)
            summaries = [
                LeadSummary(
                    lead_id=lead["lead_id"],
                    name=lead["name"],
                    status=lead["status"],
                    phone=lead.get("phone"),
                    email=lead.get("email"),
                    source=lead.get("source"),
                    created_at=lead["created_at"],
                )
                for lead in leads
            ]
            return LeadListResponse(total=len(summaries), items=summaries)

        try:
            payload = request.model_dump()
            data = await self._client.post("/leads/list", payload)
            return LeadListResponse(**data)
        except ServiceError:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Unexpected error while listing leads")
            raise ServiceError("Failed to list leads", cause=exc)
