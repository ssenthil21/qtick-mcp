from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List

from app.clients.java import JavaServiceClient
from app.schemas.lead import (
    LeadCreateRequest,
    LeadCreateResponse,
    LeadListRequest,
    LeadListResponse,
    LeadSummary,
)
from app.services.exceptions import ServiceError
from app.services.mock_store import LeadRepository

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
        print(self._client)
        print(self._repository)
        if self._client.use_mock_data and self._repository is None:
            raise RuntimeError(
                "LeadService requires a repository when mock mode is enabled. "
                "Set QTICK_USE_MOCK_DATA=false (or USE_MOCK_DATA=false) and "
                "configure QTICK_JAVA_SERVICE_BASE_URL to call the Java service. "
                "Provide QTICK_JAVA_SERVICE_TOKEN (or JAVA_SERVICE_TOKEN) if a "
                "bearer token is required."
            )

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
            now_iso = _utc_now_iso()
            follow_up_date = request.follow_up_date or now_iso
            enquired_on = request.enquired_on or now_iso
            enquiry_for_time = request.enquiry_for_time or now_iso

            details_lines: List[str] = []
            if request.details:
                details_lines.append(request.details)
            if request.notes and request.notes not in details_lines:
                details_lines.append(request.notes)
            if request.source and request.source not in ("", None):
                details_lines.append(f"Source: {request.source}")

            payload: Dict[str, Any] = {
                "bizId": request.business_id,
                "phone": request.phone.replace('+', ''),
                "custName": request.name,
                "location": request.location,
                "enqFor": request.enquiry_for,
                "srcChannel": _map_source_to_channel(request.source),
                "campId": 38,
                "campName": 'Campaign',
                "location":"Serangoon",
                "enqFor":"Offer",
                "details": "",
                "thdStatus": "A",
                "interest": 3,
                "followUpDate": follow_up_date,
                "enquiredOn": enquired_on,
                "enqForTime": enquiry_for_time,
                "attnStaffId": request.attention_staff_id or 21,
                "attnChannel": request.attention_channel or "P",
            }
            payload = _filter_payload(payload, preserve_keys={"campId", "campName"})

            data = await self._client.post("/biz/sales-enq", payload)
            
            record = {
                "bizId": data.get("bizId"),
                "custId": data.get("custId"),
                "enqNo": data.get("enqNo"),
                "custName": data.get("custName"),
                "phone": data.get("phone"),
                "enqFor": data.get("enqFor"),
                "status": data.get("status"),
                "followUpDate": data.get("followUpDate"),
                "thdStatus": data.get("thdStatus"),
                "threadCount": data.get("threadCount"),
            }
            
            print(record)
            return LeadCreateResponse(
                lead_id=str(record["bizId"]),         # fixed
                status=str(record["status"]), 
                created_at=str(enquired_on),
                next_action=str("Followup"),
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
            params = {
                "searchText": "",
                "status": "",
                "periodType": "",
                "periodFilterBy": "A",
                "fromDate": "",
                "toDate": "",
            }
            data = await self._client.get(
                f"/biz/{request.business_id}/sales-enq/list", params=params
            )
            print(data)
            
            leads: List[LeadSummary] = []

            for item in data:
                lead = LeadSummary(
                    lead_id=str(item.get("enqNo")),           # using enqNo as unique lead id
                    name=item.get("custName", ""),
                    status=str(item.get("status", "")),
                    created_at=item.get("enquiredOn", ""),
                    phone=item.get("phone"),
                    email=None,                               # Java API doesn’t have email field
                    source=item.get("srcChannel")
                )
                leads.append(lead)

            return LeadListResponse(
                total=len(leads),
                items=leads
            )
            
        except ServiceError:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Unexpected error while listing leads")
            raise ServiceError("Failed to list leads", cause=exc)


def _utc_now_iso() -> str:
    # Get current UTC time
    dt = datetime.now(timezone.utc)

    # Format as desired: 2025-09-23T04:30:00.000+0000
    formatted = dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "+0000"
    return formatted

def _map_source_to_channel(source: str | None) -> str:
    if not source:
        return "WA"
    value = source.strip().lower()
    if not value:
        return "WA"

    mapping = {
        "whatsapp": "WA",
        "wa": "WA",
        "walk-in": "P",
        "walkin": "P",
        "phone": "P",
        "call": "P",
        "manual": "P",
        "instagram": "IG",
        "ig": "IG",
        "facebook": "FB",
        "fb": "FB",
        "referral": "RF",
        "website": "WB",
    }
    return mapping.get(value, "WA")


def _filter_payload(
    payload: Dict[str, Any], *, preserve_keys: Iterable[str] | None = None
) -> Dict[str, Any]:
    preserve = set(preserve_keys or [])
    return {
        key: value
        for key, value in payload.items()
        if value is not None or key in preserve
    }


def _looks_like_lead_record(data: Dict[str, Any]) -> bool:
    identifier_keys = {"lead_id", "leadId", "enqId", "id", "uuid"}
    has_identifier = any(key in data for key in identifier_keys)
    if not has_identifier:
        return False
    return any(
        key in data for key in ("custName", "name", "customerName", "status", "thdStatus")
    )


def _extract_lead_record(data: Any) -> Dict[str, Any] | None:
    if isinstance(data, dict):
        if _looks_like_lead_record(data):
            return data
        for key in ("data", "result", "lead", "payload", "response"):
            nested = data.get(key)
            record = _extract_lead_record(nested)
            if record:
                return record
        return None
    if isinstance(data, list):
        for item in data:
            record = _extract_lead_record(item)
            if record:
                return record
    return None


def _extract_lead_items(data: Any) -> List[Dict[str, Any]]:
    if isinstance(data, list):
        items: List[Dict[str, Any]] = []
        for item in data:
            if isinstance(item, dict):
                items.append(item)
            else:
                items.extend(_extract_lead_items(item))
        return items
    if isinstance(data, dict):
        if _looks_like_lead_record(data):
            return [data]
        for key in (
            "items",
            "data",
            "result",
            "leads",
            "list",
            "records",
            "content",
            "payload",
            "response",
        ):
            nested = data.get(key)
            if nested is None:
                continue
            items = _extract_lead_items(nested)
            if items:
                return items
    return []


def _extract_total(data: Any, fallback: int) -> int:
    value = _find_first_numeric(
        data, {"total", "count", "totalCount", "totalRecords", "totalElements"}
    )
    return value if value is not None else fallback


def _find_first_numeric(data: Any, keys: Iterable[str]) -> int | None:
    if isinstance(data, dict):
        for key in keys:
            value = data.get(key)
            if isinstance(value, int):
                return value
        for value in data.values():
            found = _find_first_numeric(value, keys)
            if found is not None:
                return found
    elif isinstance(data, list):
        for item in data:
            found = _find_first_numeric(item, keys)
            if found is not None:
                return found
    return None
