
import asyncio
import ast
import json
from functools import lru_cache
import os
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query
from google.api_core.exceptions import NotFound as GoogleAPINotFound

from app.config import Settings, get_settings
from app.schemas.agent import AgentRunRequest, AgentRunResponse, AgentToolsResponse
from app.services.agent_logging import AgentLoggingCallbackHandler, AgentRunCollector

from app.services.conversation_memory import ConversationTurn, conversation_memory
from langchain.agents import AgentType, initialize_agent
from langchain_google_genai import ChatGoogleGenerativeAI

from langchain_tools.qtick import (
    analytics_tool,
    business_search_tool,
    business_service_lookup_tool,
    appointment_list_tool,
    appointment_tool,
    campaign_tool,
    configure,
    datetime_tool,
    invoice_create_tool,
    invoice_list_tool,
    lead_create_tool,
    lead_list_tool,
)

router = APIRouter()


_TOOL_DISPLAY_NAMES: Dict[str, str] = {
    "appointment_book": "Appointment",
    "appointment_list": "Appointment List",
    "invoice_create": "Invoice",
    "invoice_list": "Invoice List",
    "lead_create": "Lead",
    "lead_list": "Lead List",
    "business_search": "Business Search",
    "business_service_lookup": "Service Lookup",
    "campaign_send_whatsapp": "Campaign",
    "analytics_report": "Analytics",
    "datetime_parse": "Datetime",
}


def _cache_key(settings: Settings) -> Tuple[str, str, float]:
    return (str(settings.mcp_base_url), settings.agent_google_model, settings.agent_temperature)


def _build_tools() -> List:
    return [
        datetime_tool(),
        business_search_tool(),
        business_service_lookup_tool(),
        appointment_tool(),
        appointment_list_tool(),
        invoice_list_tool(),
        invoice_create_tool(),
        lead_create_tool(),
        lead_list_tool(),
        campaign_tool(),
        analytics_tool(),
    ]


def _display_name(tool_name: Optional[str]) -> Optional[str]:
    if not tool_name:
        return None
    if tool_name in _TOOL_DISPLAY_NAMES:
        return _TOOL_DISPLAY_NAMES[tool_name]
    return tool_name.replace("_", " ").title()


def _strip_nones(data: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in data.items() if v not in (None, [], {})}



def _format_conversation_history(history: List[ConversationTurn]) -> str:
    lines: List[str] = []
    for turn in history:
        if turn.user:
            lines.append(f"User: {turn.user}")
        if turn.assistant:
            lines.append(f"Assistant: {turn.assistant}")
    return "\n".join(lines)



def _build_prompt_with_history(prompt: str, history: List[ConversationTurn]) -> str:
    if not history:
        return prompt
    history_text = _format_conversation_history(history)
    return (
        "You are continuing a conversation with the user. Use the previous "
        "messages to maintain context when deciding on tool calls or crafting "
        "the final answer. The history is ordered from oldest to newest.\n\n"
        f"Conversation so far:\n{history_text}\n\n"
        f"Latest user request: {prompt}"
    )


def _safe_parse_string(value: str) -> Any:
    text = value.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        try:
            return ast.literal_eval(text)
        except (ValueError, SyntaxError):
            return text


def _normalize_io(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        return value.model_dump()  # type: ignore[call-arg]
    if hasattr(value, "dict"):
        return value.dict()  # type: ignore[call-arg]
    if isinstance(value, str):
        parsed = _safe_parse_string(value)
        return parsed
    return value


def _prune_nones(value: Any) -> Any:
    """Recursively drop ``None`` values from nested structures."""

    if isinstance(value, dict):
        return {k: _prune_nones(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [_prune_nones(item) for item in value if item is not None]
    return value


def _normalize_pending_tool_input(value: Any) -> Optional[Dict[str, Any]]:
    """Convert pending tool payloads into a JSON-serialisable dict."""

    normalized = _normalize_io(value)
    if normalized is None:
        return None
    if isinstance(normalized, dict):
        return _prune_nones(normalized)
    return {"value": normalized}


def _summarize_appointment_book(
    output: Dict[str, Any], tool_input: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    base: Dict[str, Any] = {
        "status": output.get("status"),
        "appointmentId": output.get("appointment_id"),
        "queueNumber": output.get("queue_number"),
    }
    message = output.get("message")
    if message:
        base["message"] = message
    suggestions = output.get("suggested_slots")
    if suggestions:
        base["suggestedSlots"] = suggestions
    if tool_input:
        base.update(
            {
                "businessId": tool_input.get("business_id"),
                "customer": tool_input.get("customer_name"),
                "serviceId": tool_input.get("service_id"),
                "datetime": tool_input.get("datetime"),
            }
        )
    return _strip_nones(base)


def _summarize_appointment_list(output: Dict[str, Any]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    summary = _strip_nones(
        {
            "total": output.get("total"),
            "page": output.get("page"),
            "pageSize": output.get("page_size"),
        }
    )
    if summary:
        items.append(summary)
    for item in output.get("items", []) or []:
        if isinstance(item, dict):
            items.append(
                _strip_nones(
                    {
                        "appointmentId": item.get("appointment_id"),
                        "customer": item.get("customer_name"),
                        "serviceId": item.get("service_id"),
                        "datetime": item.get("datetime"),
                        "status": item.get("status"),
                        "queueNumber": item.get("queue_number"),
                    }
                )
            )
    return items


def _summarize_invoice_create(
    output: Dict[str, Any], tool_input: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    base: Dict[str, Any] = {
        "invoiceId": output.get("invoice_id"),
        "total": output.get("total"),
        "currency": output.get("currency"),
        "status": output.get("status"),
        "createdAt": output.get("created_at"),
        "paymentLink": output.get("payment_link"),
    }
    business_id = output.get("business_id")
    if business_id is not None:
        base["businessId"] = business_id
    if tool_input:
        items_payload: List[Dict[str, Any]] = []
        for item in tool_input.get("items", []) or []:
            if isinstance(item, dict):
                unit_price = item.get("unit_price")
                if unit_price is None:
                    unit_price = item.get("price")
                items_payload.append(
                    _strip_nones(
                        {
                            "description": item.get("description"),
                            "quantity": item.get("quantity"),
                            "unitPrice": unit_price,
                            "taxRate": item.get("tax_rate"),
                        }
                    )
                )
        if items_payload:
            base["items"] = items_payload
        base.setdefault("customer", tool_input.get("customer_name"))
        base.setdefault("businessId", tool_input.get("business_id"))
        base.setdefault("currency", tool_input.get("currency"))
    return _strip_nones(base)


def _summarize_invoice_list(output: Dict[str, Any]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    summary = _strip_nones({"total": output.get("total")})
    if summary:
        items.append(summary)
    for item in output.get("items", []) or []:
        if isinstance(item, dict):
            items.append(
                _strip_nones(
                    {
                        "invoiceId": item.get("invoice_id"),
                        "total": item.get("total"),
                        "currency": item.get("currency"),
                        "createdAt": item.get("created_at"),
                        "status": item.get("status"),
                    }
                )
            )
    return items


def _summarize_lead_create(output: Dict[str, Any], tool_input: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    base: Dict[str, Any] = {
        "leadId": output.get("lead_id"),
        "status": output.get("status"),
        "createdAt": output.get("created_at"),
        "nextAction": output.get("next_action"),
        "followUpRequired": output.get("follow_up_required"),
    }
    if tool_input:
        base.setdefault("customer", tool_input.get("name"))
        base.setdefault("businessId", tool_input.get("business_id"))
        base.setdefault("phone", tool_input.get("phone"))
        base.setdefault("email", tool_input.get("email"))
        base.setdefault("source", tool_input.get("source"))
    return _strip_nones(base)


def _summarize_lead_list(output: Dict[str, Any]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    summary = _strip_nones({"total": output.get("total")})
    if summary:
        items.append(summary)
    for item in output.get("items", []) or []:
        if isinstance(item, dict):
            items.append(_strip_nones({
                "leadId": item.get("lead_id"),
                "status": item.get("status"),
                "createdAt": item.get("created_at"),
                "customer": item.get("name"),
                "phone": item.get("phone"),
                "email": item.get("email"),
            }))
    return items


def _summarize_business_search(output: Dict[str, Any]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    summary = _strip_nones({"query": output.get("query"), "total": output.get("total")})
    if summary:
        items.append(summary)

    for business in output.get("items", []) or []:
        if isinstance(business, dict):
            payload = _strip_nones(
                {
                    "businessId": business.get("business_id"),
                    "name": business.get("name"),
                    "location": business.get("location"),
                    "tags": business.get("tags"),
                }
            )
            if payload:
                items.append(payload)

    message = output.get("message")
    if message:
        items.append({"message": message})

    return items


def _summarize_service_lookup(output: Dict[str, Any]) -> List[Dict[str, Any]]:
    business_payload: Optional[Dict[str, Any]] = None
    business = output.get("business")
    if isinstance(business, dict):
        business_payload = _strip_nones(
            {
                "businessId": business.get("business_id"),
                "name": business.get("name"),
                "location": business.get("location"),
                "tags": business.get("tags"),
            }
        )

    matches_payload: List[Dict[str, Any]] = []
    for match in output.get("matches") or []:
        if isinstance(match, dict):
            match_payload = _strip_nones(
                {
                    "serviceId": match.get("service_id"),
                    "name": match.get("name"),
                    "category": match.get("category"),
                    "durationMinutes": match.get("duration_minutes"),
                    "price": match.get("price"),
                }
            )
            if match_payload:
                matches_payload.append(match_payload)

    service_match_groups: List[Dict[str, Any]] = []
    for group in output.get("service_matches") or []:
        if isinstance(group, dict):
            business_info = group.get("business")
            services = group.get("services") or []
            business_payload = None
            if isinstance(business_info, dict):
                business_payload = _strip_nones(
                    {
                        "businessId": business_info.get("business_id"),
                        "name": business_info.get("name"),
                        "location": business_info.get("location"),
                        "tags": business_info.get("tags"),
                    }
                )
            services_payload: List[Dict[str, Any]] = []
            for item in services:
                if isinstance(item, dict):
                    service_payload = _strip_nones(
                        {
                            "serviceId": item.get("service_id"),
                            "name": item.get("name"),
                            "category": item.get("category"),
                            "durationMinutes": item.get("duration_minutes"),
                            "price": item.get("price"),
                        }
                    )
                    if service_payload:
                        services_payload.append(service_payload)
            payload = _strip_nones(
                {
                    "business": business_payload,
                    "services": services_payload or None,
                }
            )
            if payload:
                service_match_groups.append(payload)

    business_candidates_payload: List[Dict[str, Any]] = []
    for candidate in output.get("business_candidates") or []:
        if isinstance(candidate, dict):
            candidate_payload = _strip_nones(
                {
                    "businessId": candidate.get("business_id"),
                    "name": candidate.get("name"),
                    "location": candidate.get("location"),
                    "tags": candidate.get("tags"),
                }
            )
            if candidate_payload:
                business_candidates_payload.append(candidate_payload)

    exact_match_payload: Optional[Dict[str, Any]] = None
    exact_match = output.get("exact_match")
    if isinstance(exact_match, dict):
        exact_match_payload = _strip_nones(
            {
                "serviceId": exact_match.get("service_id"),
                "name": exact_match.get("name"),
                "category": exact_match.get("category"),
                "durationMinutes": exact_match.get("duration_minutes"),
                "price": exact_match.get("price"),
            }
        )

    summary = _strip_nones(
        {
            "query": output.get("query"),
            "business": business_payload,
            "matches": matches_payload or None,
            "exactMatch": exact_match_payload,
            "message": output.get("message"),
            "businessCandidates": business_candidates_payload or None,
            "serviceMatches": service_match_groups or None,
            "suggestedServices": output.get("suggested_service_names"),
        }
    )

    if matches_payload:
        summary["matches"] = matches_payload
    if business_candidates_payload:
        summary["businessCandidates"] = business_candidates_payload
    if service_match_groups:
        summary["serviceMatches"] = service_match_groups
    suggestions = output.get("suggested_service_names")
    if suggestions:
        summary["suggestedServices"] = suggestions

    return [summary] if summary else []


def _summarize_campaign(output: Dict[str, Any], tool_input: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    base: Dict[str, Any] = {
        "status": output.get("status"),
        "deliveryTime": output.get("delivery_time"),
    }
    if tool_input:
        base.setdefault("customer", tool_input.get("customer_name"))
        base.setdefault("phoneNumber", tool_input.get("phone_number"))
        base.setdefault("offerCode", tool_input.get("offer_code"))
        base.setdefault("expiry", tool_input.get("expiry"))
    return _strip_nones(base)


def _summarize_analytics(output: Dict[str, Any]) -> Dict[str, Any]:
    summary: Dict[str, Any] = {
        "footfall": output.get("footfall"),
        "revenue": output.get("revenue"),
        "reportGeneratedAt": output.get("report_generated_at"),
    }

    top_service = output.get("top_appointment_service")
    if isinstance(top_service, dict):
        summary["topAppointmentService"] = _strip_nones(
            {
                "serviceId": top_service.get("service_id"),
                "name": top_service.get("name"),
                "bookingCount": top_service.get("booking_count"),
            }
        )

    highest_revenue = output.get("highest_revenue_service")
    if isinstance(highest_revenue, dict):
        summary["highestRevenueService"] = _strip_nones(
            {
                "serviceId": highest_revenue.get("service_id"),
                "name": highest_revenue.get("name"),
                "totalRevenue": highest_revenue.get("total_revenue"),
                "currency": highest_revenue.get("currency"),
            }
        )

    appointment_summary = output.get("appointment_summary")
    if isinstance(appointment_summary, dict):
        summary["appointmentSummary"] = _strip_nones(
            {
                "total": appointment_summary.get("total"),
                "byStatus": appointment_summary.get("by_status"),
                "uniqueCustomers": appointment_summary.get("unique_customers"),
            }
        )

    invoice_summary = output.get("invoice_summary")
    if isinstance(invoice_summary, dict):
        summary["invoiceSummary"] = _strip_nones(
            {
                "total": invoice_summary.get("total"),
                "byStatus": invoice_summary.get("by_status"),
                "totalRevenue": invoice_summary.get("total_revenue"),
                "paidTotal": invoice_summary.get("paid_total"),
                "outstandingTotal": invoice_summary.get("outstanding_total"),
                "averageInvoiceValue": invoice_summary.get("average_invoice_value"),
                "currency": invoice_summary.get("currency"),
                "uniqueCustomers": invoice_summary.get("unique_customers"),
            }
        )

    lead_summary = output.get("lead_summary")
    if isinstance(lead_summary, dict):
        summary["leadSummary"] = _strip_nones(
            {
                "total": lead_summary.get("total"),
                "byStatus": lead_summary.get("by_status"),
                "sourceBreakdown": lead_summary.get("source_breakdown"),
            }
        )

    return _strip_nones(summary)


def _summarize_datetime(output: Dict[str, Any]) -> Dict[str, Any]:
    return _strip_nones(output)


def summarize_tool_result(
    tool_name: Optional[str], tool_input: Any, tool_output: Any
) -> tuple[Optional[str], List[Dict[str, Any]]]:
    display_name = _display_name(tool_name)
    normalized_input = _normalize_io(tool_input)
    normalized_output = _normalize_io(tool_output)

    input_dict = normalized_input if isinstance(normalized_input, dict) else None
    output_dict = normalized_output if isinstance(normalized_output, dict) else None

    data_points: List[Dict[str, Any]] = []

    if isinstance(normalized_output, list):
        for entry in normalized_output:
            if isinstance(entry, dict):
                data_points.append(_strip_nones(entry))
        return display_name, data_points

    if tool_name == "appointment_book" and output_dict is not None:
        data_points.append(_summarize_appointment_book(output_dict, input_dict))
    elif tool_name == "appointment_list" and output_dict is not None:
        data_points.extend(_summarize_appointment_list(output_dict))
    elif tool_name == "invoice_create" and output_dict is not None:
        data_points.append(_summarize_invoice_create(output_dict, input_dict))
    elif tool_name == "invoice_list" and output_dict is not None:
        data_points.extend(_summarize_invoice_list(output_dict))
    elif tool_name == "lead_create" and output_dict is not None:
        data_points.append(_summarize_lead_create(output_dict, input_dict))
    elif tool_name == "lead_list" and output_dict is not None:
        data_points.extend(_summarize_lead_list(output_dict))
    elif tool_name == "business_search" and output_dict is not None:
        data_points.extend(_summarize_business_search(output_dict))
    elif tool_name == "business_service_lookup" and output_dict is not None:
        data_points.extend(_summarize_service_lookup(output_dict))
    elif tool_name == "campaign_send_whatsapp" and output_dict is not None:
        data_points.append(_summarize_campaign(output_dict, input_dict))
    elif tool_name == "analytics_report" and output_dict is not None:
        data_points.append(_summarize_analytics(output_dict))
    elif tool_name == "datetime_parse" and output_dict is not None:
        data_points.append(_summarize_datetime(output_dict))
    elif output_dict is not None:
        data_points.append(_strip_nones(output_dict))
    elif normalized_output not in (None, ""):
        data_points.append({"value": normalized_output})

    return display_name, data_points


@lru_cache(maxsize=1)
def _get_agent_bundle(cache_key: Tuple[str, str, float]):
    settings = get_settings()
    configure(
        base_url=str(settings.mcp_base_url), timeout=settings.agent_tool_timeout
    )
    if settings.google_api_key:
        os.environ.setdefault("GOOGLE_API_KEY", settings.google_api_key)
    elif not os.getenv("GOOGLE_API_KEY"):
        raise HTTPException(status_code=500, detail="GOOGLE_API_KEY not set on server")

    llm = ChatGoogleGenerativeAI(
        model=settings.agent_google_model,
        temperature=settings.agent_temperature,
    )
    tools = _build_tools()
    agent = initialize_agent(
        tools=tools,
        llm=llm,
        agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
        verbose=False,
        callbacks=[AgentLoggingCallbackHandler()],
    )
    return agent, tools


def _get_agent(settings: Settings) -> Tuple[object, List]:
    cache_key = _cache_key(settings)
    return _get_agent_bundle(cache_key)


@router.post("/run", response_model=AgentRunResponse)
async def run_agent(
    req: AgentRunRequest,
    settings: Settings = Depends(get_settings),
):
    try:
        agent, _ = _get_agent(settings)
        collector = AgentRunCollector()

        conversation_id = req.conversation_id
        if conversation_id and req.reset_conversation:
            conversation_memory.reset(conversation_id)

        history: List[ConversationTurn] = []
        if conversation_id:
            history = conversation_memory.get_history(conversation_id)

        prompt_with_history = _build_prompt_with_history(req.prompt, history)

        def _execute(prompt: str) -> str:
            return agent.run(prompt, callbacks=[collector])

        output = await asyncio.to_thread(_execute, prompt_with_history)
        tool_name, data_points = summarize_tool_result(
            collector.tool_name, collector.tool_input, collector.tool_output
        )

        requires_human = collector.tool_name == "invoice_create"
        pending_tool = collector.tool_name if requires_human else None
        pending_tool_input = (
            _normalize_pending_tool_input(collector.tool_input)
            if requires_human
            else None
        )

        final_output = collector.final_output or output
        if conversation_id:
            conversation_memory.append(conversation_id, req.prompt, final_output)

        return AgentRunResponse(
            output=output,
            tool=tool_name,
            data_points=data_points,
            requires_human=requires_human,
            pending_tool=pending_tool,
            pending_tool_input=pending_tool_input,
        )
    except HTTPException:
        raise
    except GoogleAPINotFound as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "Agent model is unavailable. Configure QTICK_AGENT_GOOGLE_MODEL "
                "to a supported model such as 'gemini-2.5-flash'. Original error: "
                f"{exc}"
            ),
        ) from exc
    except Exception as exc:  # pragma: no cover - runtime dependency
        raise HTTPException(status_code=500, detail=f"Agent error: {exc}") from exc


@router.get("/run", response_model=AgentRunResponse)
async def run_agent_get(
    prompt: str = Query(..., description="Your natural language instruction"),
    conversation_id: Optional[str] = Query(None, alias="conversationId"),
    reset_conversation: bool = Query(False, alias="resetConversation"),
    settings: Settings = Depends(get_settings),
):
    return await run_agent(
        AgentRunRequest(
            prompt=prompt,
            conversation_id=conversation_id,
            reset_conversation=reset_conversation,
        ),
        settings,
    )


@router.get("/tools", response_model=AgentToolsResponse)
async def list_agent_tools(settings: Settings = Depends(get_settings)):
    _, tools = _get_agent(settings)
    return AgentToolsResponse(
        tools=[{"name": tool.name, "description": tool.description} for tool in tools]
    )
