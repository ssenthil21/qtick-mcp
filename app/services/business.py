from __future__ import annotations

import logging

from app.clients.java import JavaServiceClient
from app.schemas.business import (
    BusinessSearchRequest,
    BusinessSearchResponse,
    BusinessServiceMatch,
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

            if not request.business_id and not request.business_name:
                grouped = self._repository.find_businesses_for_service(
                    request.service_name, request.limit
                )
                if not grouped:
                    return ServiceLookupResponse(
                        query=request.service_name,
                        message="No businesses currently offer a service with that name.",
                        service_matches=[],
                    )

                if len(grouped) == 1:
                    business_summary, matches = grouped[0]
                    exact = next(
                        (
                            match
                            for match in matches
                            if match.name.lower() == request.service_name.lower()
                        ),
                        None,
                    )
                    message = (
                        "Found one business offering this service."
                        if exact
                        else "Found one business with related services."
                    )
                    return ServiceLookupResponse(
                        query=request.service_name,
                        business=business_summary,
                        matches=matches,
                        exact_match=exact,
                        message=message,
                    )

                groups = [
                    BusinessServiceMatch(business=summary, services=matches)
                    for summary, matches in grouped
                ]
                message = (
                    "Multiple businesses offer this service. Please choose the intended business."
                )
                return ServiceLookupResponse(
                    query=request.service_name,
                    business_candidates=[group.business for group in groups],
                    service_matches=groups,
                    message=message,
                )

            business_record = None
            business_candidates: list[BusinessSummary] | None = None
            if request.business_id:
                business_record = self._repository.get_business(request.business_id)
                if not business_record:
                    raise ServiceError(
                        f"Business '{request.business_id}' not found in master data"
                    )
            else:
                business_candidates = self._repository.find_businesses_by_name(
                    request.business_name or ""
                )
                if not business_candidates:
                    raise ServiceError(
                        f"Business '{request.business_name}' not found in master data"
                    )
                if len(business_candidates) > 1:
                    return ServiceLookupResponse(
                        query=request.service_name,
                        business_candidates=business_candidates,
                        message=(
                            "Multiple businesses matched the provided name. Please choose the correct business before searching services."
                        ),
                    )
                business_record = self._repository.get_business(
                    business_candidates[0].business_id
                )
                if not business_record:
                    raise ServiceError(
                        f"Business '{business_candidates[0].business_id}' not found in master data"
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
            normalized_compact = normalized_query.replace(" ", "").replace("-", "")
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

            hair_tokens = normalized_query.replace("-", " ").split()
            is_haircut_query = "haircut" in normalized_compact or (
                "hair" in hair_tokens and "cut" in hair_tokens
            )

            if is_haircut_query and business_record.services:
                haircut_names = [
                    service.name
                    for service in business_record.services
                    if "hair" in service.name.lower()
                ]
                if haircut_names:
                    hair_msg = (
                        "Please specify which haircut service you need. Available haircut services: "
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
