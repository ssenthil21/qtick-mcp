from __future__ import annotations

import logging

from app.clients.java import JavaServiceClient
from app.schemas.business import (
    BusinessSearchRequest,
    BusinessSearchResponse,
    BusinessSummary,
    ServiceLookupRequest,
    ServiceLookupResponse,
)
from app.services.exceptions import ServiceError
from app.services.mock_store import MasterDataRepository, get_mock_store

logger = logging.getLogger(__name__)


class BusinessDirectoryService:
    """Service responsible for business and service master data queries."""

    def __init__(
        self,
        client: JavaServiceClient,
        *,
        repository: MasterDataRepository | None = None,
    ) -> None:
        self._client = client
        self._repository = repository
        if self._client.use_mock_data:
            self._repository = repository or get_mock_store().master_data

    async def search(self, request: BusinessSearchRequest) -> BusinessSearchResponse:
        logger.info("Searching businesses for query '%s'", request.query)
        if self._client.use_mock_data:
            await self._client.simulate_latency()
            if not self._repository:
                raise RuntimeError("Mock master data repository not configured")
            return self._repository.search_businesses(request.query, request.limit)

        raise ServiceError("Business search is not available in live mode yet")

    async def lookup_service(
        self, request: ServiceLookupRequest
    ) -> ServiceLookupResponse:
        logger.info(
            "Looking up service '%s' for business selector (%s, %s)",
            request.service_name,
            request.business_id,
            request.business_name,
        )
        if self._client.use_mock_data:
            await self._client.simulate_latency()
            if not self._repository:
                raise RuntimeError("Mock master data repository not configured")

            business_identifier = request.business_id or request.business_name
            assert business_identifier is not None  # for mypy
            business_record = self._repository.get_business(business_identifier)
            if not business_record:
                raise ServiceError(
                    f"Business '{business_identifier}' not found in master data"
                )

            matches = self._repository.find_services(
                business_record, request.service_name, request.limit
            )
            exact = next(
                (match for match in matches if match.name.lower() == request.service_name.lower()),
                None,
            )

            message: str | None = None
            normalized_query = request.service_name.strip().lower()
            if not matches:
                message = "No matching services were found. Try a different keyword."
            elif len(matches) > 1 and not exact:
                message = (
                    "Multiple services matched your search. Please choose the most appropriate option."
                )
            elif len(matches) > 1 and exact:
                message = (
                    "Multiple services found including an exact name match; confirm the intended service."
                )

            if "haircut" in normalized_query and business_record.services:
                haircut_names = [
                    service.name
                    for service in business_record.services
                    if "hair" in service.name.lower()
                ]
                if haircut_names:
                    hair_msg = (
                        "Available haircut services: "
                        + ", ".join(sorted(haircut_names))
                    )
                    message = f"{message} {hair_msg}".strip() if message else hair_msg

            business_summary = BusinessSummary(
                business_id=business_record.business_id,
                name=business_record.name,
                location=business_record.location,
                tags=list(business_record.tags),
            )

            return ServiceLookupResponse(
                query=request.service_name,
                business=business_summary,
                matches=matches,
                exact_match=exact,
                message=message,
            )

        raise ServiceError("Service lookup is not available in live mode yet")
