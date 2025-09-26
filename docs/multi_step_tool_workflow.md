# Multi-step LLM Tool Workflow with QTick MCP

This guide explains how to let an LLM handle a natural language request, decide which MCP tools to call, and then use the tool output to answer a follow-up question. While the original example walked through "List today's appointments and tell me the contact number for each person", the same pattern works for any business object that QTick exposes—appointments, invoices, leads, and reviews.

The sections below show how to make the workflow generic so the LLM can field prompts such as:

- "From today's invoices tell me the highest paid service"
- "From today's appointments give me the top 5 services"
- "From the leads share the phone number"
- "From the leads group by lead source"
- "Summarise the latest reviews triggered after payments"

## 1. Catalogue the MCP tool schemas

Start by cataloguing every data-bearing MCP tool that your agent can reach. QTick already exposes endpoints for the key business objects and keeps the FastMCP function names aligned with the REST catalogue:

| Object | FastMCP tool name | REST tool name | Key fields returned |
| --- | --- | --- | --- |
| Appointment | `appointments_list` | `appointments.list` (`/tools/appointment/list`) | `id`, `customer_name`, `service`, `start_time`, `status`【F:app/mcp_server.py†L13-L48】【F:app/tools/mcp.py†L45-L70】【F:app/tools/appointment.py†L15-L33】 |
| Invoice | `invoice_create` (FastMCP currently exposes create) | `invoice.list` (`/tools/invoice/list`) | `invoice_id`, `customer_name`, `total`, `status`, `items`【F:app/mcp_server.py†L60-L103】【F:app/tools/mcp.py†L81-L117】【F:app/tools/invoice.py†L17-L39】【F:app/services/invoice.py†L51-L71】 |
| Lead | `leads_create` (FastMCP currently exposes create) | `leads.list` (`/tools/leads/list`) | `lead_id`, `name`, `phone`, `email`, `source`【F:app/mcp_server.py†L104-L108】【F:app/tools/mcp.py†L118-L146】【F:app/tools/leads.py†L16-L33】 |
| Review | *(Planned FastMCP surface via live ops)* | `live_ops.events` (`/tools/live-ops/events`) | Events for review requests triggered by invoice payments, including `customer_name`, `status`, and timestamps【F:app/tools/mcp.py†L147-L189】【F:app/tools/live_ops.py†L1-L18】【F:app/services/live_ops.py†L83-L184】 |

> **Tip:** The MCP server also exposes create/update tools (e.g. `invoice_create`, `invoice.mark_paid`, `leads_create`) that enrich the schema definitions for downstream reasoning.【F:app/mcp_server.py†L60-L108】【F:app/tools/mcp.py†L92-L143】 Even if you only need read-only answers, inspecting these schemas tells the model which attributes exist.

Keep this catalogue close to your planner prompt so the LLM knows which tool to pick once it detects the business object mentioned in the user's query.

## 2. Instruct the model to plan before calling tools

When you prompt the LLM, remind it to plan: identify which tools are required, gather missing context (e.g., date ranges), and combine the results into the final answer. For OpenAI-style function calling, a system prompt similar to the snippet below works well:

```text
You are a QTick assistant. Think step by step. If the user request requires data, decide which MCP tool to call. When you have enough information, respond with a helpful summary that answers the user directly.
```

Include a quick reference to the tool catalogue so the LLM can map "appointments", "invoices", "leads", or "reviews" to the correct tool names.

## 3. Parse the user's question into tool arguments

Natural language like "today" must be converted into ISO 8601 dates. You can reuse the parsing helpers already available in the LangChain tool wrapper (`langchain_tools/qtick.py`), which shows how to normalise date strings and enforce ISO formatting before calling the REST endpoint.【F:langchain_tools/qtick.py†L1-L116】

For generic reasoning, build a lightweight intent parser that extracts:

1. The business object (appointment, invoice, lead, review).
2. The analytical instruction (e.g., "highest paid service", "top 5 services", "group by lead source").
3. Any filters (dates, statuses, revenue thresholds).

Feed those pieces into a dispatcher that knows which MCP tool arguments to populate.

## 4. Example multi-entity controller

The controller below demonstrates how to normalise intents, call the correct tool, and hand the structured rows back to the LLM. It uses the SSE transport exposed by `app.main` so the same logic works for invoices, appointments, leads, or reviews regardless of whether you host the MCP server locally or remotely:

```python
import asyncio
from collections.abc import Awaitable, Callable
from datetime import date
from typing import Any, Dict, List

from mcp.client.session import ClientSession
from mcp.client.sse import sse_client


def _date_range_for_today() -> Dict[str, str]:
    today = date.today().isoformat()
    return {"date_from": today, "date_to": today}


ENTITY_TOOL: Dict[str, Dict[str, Any]] = {
    "appointment": {
        "fastmcp": "appointments_list",
        "rest": "appointments.list",
        "argument_builder": lambda business_id: {
            "business_id": business_id,
            **_date_range_for_today(),
        },
    },
    "invoice": {
        "fastmcp": "invoice_create",  # Until FastMCP ships `invoice_list`, use REST for reads.
        "rest": "invoice.list",
        "argument_builder": lambda business_id: {"business_id": business_id},
    },
    "lead": {
        "fastmcp": "leads_create",  # Until FastMCP ships `leads_list`, use REST for reads.
        "rest": "leads.list",
        "argument_builder": lambda business_id: {"business_id": business_id},
    },
    "review": {
        "fastmcp": None,
        "rest": "live_ops.events",
        "argument_builder": lambda business_id: {
            "business_id": business_id,
            **_date_range_for_today(),
        },
    },
}


def _normalise_call_result(result: Any) -> Any:
    """Flatten `CallToolResult.content` blocks into a Python object.

    FastMCP returns the tool payload as a list of `Content` blocks. Each block
    may expose `.json` or `.text` depending on the tool. This helper converts the
    response into a single dict/list so the downstream summariser does not need
    to understand MCP internals.
    """

    blocks: List[Any] = []
    for block in getattr(result, "content", []) or []:
        if getattr(block, "json", None) is not None:
            blocks.append(block.json)
        elif getattr(block, "text", None) is not None:
            blocks.append(block.text)

    if not blocks:
        return {}
    if len(blocks) == 1:
        return blocks[0]
    return blocks


async def fetch_entity_rows(
    session: ClientSession, business_id: int, entity: str
) -> Any:
    descriptor = ENTITY_TOOL[entity]
    tool_args = descriptor["argument_builder"](business_id)
    tool_name = descriptor["fastmcp"]
    try:
        if tool_name:
            result = await session.call_tool(tool_name, tool_args)
        else:
            raise ValueError("No FastMCP surface yet")
    except Exception:
        result = await session.call_tool(descriptor["rest"], tool_args)
    return _normalise_call_result(result)


async def answer_business_question(
    session: ClientSession,
    completion_fn: Callable[[str], Awaitable[str]],
    business_id: int,
    entity: str,
    instruction: str,
) -> str:
    rows = await fetch_entity_rows(session, business_id, entity)
    summary_prompt = f"""
    You are the analyst for today's {entity}s. Follow the instruction strictly.
    Instruction: {instruction}
    Data: {rows}
    Return the result as concise bullet points or tables when appropriate.
    """
    return await completion_fn(summary_prompt)


async def run():
    async with sse_client("http://localhost:8000/sse") as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()

            async def fake_completion(prompt: str) -> str:
                # Replace with a call to your preferred LLM (OpenAI, Gemini, etc.).
                print("LLM PROMPT", prompt)
                return "<summary from LLM>"

            print(
                await answer_business_question(
                    session,
                    fake_completion,
                    business_id=42,
                    entity="invoice",
                    instruction="From today's invoices tell me the highest paid service",
                )
            )


asyncio.run(run())
```

Key ideas:

1. **Transport ready** – `sse_client` + `ClientSession` mirrors the harnesses in the repository so you can swap in stdio or TCP transports without rewriting controller logic.
2. **Tool call** – The dispatcher selects the right tool name and arguments based on the entity detected in the user query and keeps FastMCP/REST names in sync.
3. **Stateful reasoning** – After normalising the `CallToolResult`, send the structured result back to the LLM via a pluggable completion function so it can finish the task.
4. **Optional follow-up tools** – If attributes are missing (e.g., appointment rows do not include phone numbers), make an extra call such as `leads.list` before crafting the final answer.

## 5. Teach the agent to iterate

Modern agents (OpenAI, LangChain, LlamaIndex) support looped tool execution. Enable the planner/agent mode so the model can:

1. Inspect the first tool response.
2. Decide whether additional calls are required (e.g., fetching contact numbers via another tool).
3. Compose the final natural-language answer only when everything needed is available.

The existing LangChain integration in this repo already configures structured tools, so plugging the MCP endpoints into an `AgentExecutor` or `AutonomousAgent` will let the LLM perform these iterations automatically.【F:langchain_tools/qtick.py†L117-L226】

## 6. Worked examples for common prompts

Use the following patterns to cover the scenarios highlighted earlier. Each row assumes the LLM has parsed the object (appointment/invoice/lead/review) and the analytical instruction:

| User request | Tools to call | Follow-up reasoning |
| --- | --- | --- |
| "From today's invoices tell me the highest paid service" | Call `invoice.list`, filter results to today's issue date if needed, then sort line items by `total` or `unit_price` to report the maximum. | Ask the LLM to inspect each invoice's items and compute the highest `quantity * unit_price` combination. Include currency in the answer.【F:app/tools/invoice.py†L24-L32】【F:app/services/invoice.py†L59-L71】 |
| "From today's appointments give me the top 5 services" | Call `appointments_list` with a date filter covering today. | Ask the LLM to tally `service` frequency and output the top 5 entries with counts and optionally start times.【F:app/mcp_server.py†L26-L48】 |
| "From the leads share the phone number" | Call `leads.list`. | Ask the LLM to produce a table of `name` → `phone`, explicitly stating if a contact number is missing.【F:app/tools/leads.py†L16-L33】 |
| "From the leads group by lead source" | Call `leads.list`. | Have the LLM bucket the rows by `source` and return totals or percentages per source.【F:app/tools/leads.py†L16-L33】 |
| "Summarise the latest reviews triggered after payments" | Call `live_ops.events` (optionally following an `invoice.mark_paid`). | Filter the returned events to `review` entries and report customer name, status, and timestamp.【F:app/tools/mcp.py†L168-L189】【F:app/services/live_ops.py†L162-L184】 |

Because the workflow loops through "plan → call tool → analyse JSON → answer", adding a new business object is as simple as extending the dispatcher mapping and updating the planner prompt with the new schema summary.
