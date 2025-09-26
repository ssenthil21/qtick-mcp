# Multi-step LLM Tool Workflow with QTick MCP

This guide explains how to let an LLM handle a natural language request, decide which MCP tools to call, and then use the tool output to answer a follow-up question. While the original example walked through "List today's appointments and tell me the contact number for each person", the same pattern works for any business object that QTick exposes—appointments, invoices, leads, and reviews.

The sections below show how to make the workflow generic so the LLM can field prompts such as:

- "From today's invoices tell me the highest paid service"
- "From today's appointments give me the top 5 services"
- "From the leads share the phone number"
- "From the leads group by lead source"
- "Summarise the latest reviews triggered after payments"

## 0. Quick-start implementation checklist

If you are wiring this flow into a new agent for the first time, work through the following high-level tasks. Each step links to
the deeper guidance later in this document so you can iterate quickly:

1. **Bootstrap an MCP client** – Use `mcp.client.session.ClientSession` with either the SSE or Streamable HTTP transport pointed
   at your QTick MCP server and verify that `session.list_tools()` returns the expected endpoints. The repo includes integration
   test harnesses (`TEST_mcp_client.py`, `TEST_mcp_client_stream.py`, `TEST_mcp_client_sse.py`) that demonstrate both transports
   and basic connectivity checks.【F:TEST_mcp_client.py†L1-L34】【F:TEST_mcp_client_stream.py†L1-L19】【F:TEST_mcp_client_sse.py†L1-L17】
2. **Codify the tool catalogue** – Record the object → tool mapping shown below inside your planner prompt or controller so the
   model can resolve which tool to call for each entity (§1).
3. **Implement intent parsing** – Translate user utterances into `(entity, instruction, filters)` tuples using your preferred
   NLP layer (§3). Start with keyword matching, then layer in LLM-based parsing once the basic loop works.
4. **Build the dispatcher/controller** – Reuse or adapt the `ENTITY_TOOL` mapping and `fetch_entity_rows` helpers in §4 so you
   can issue tool calls with consistent arguments.
5. **Add a reasoning loop** – After each tool call, feed the JSON payload back to the LLM (via your completion API or a
   higher-level agent executor) and let it decide whether more data is needed (§5). Only once the model is satisfied should you
   stream the final answer to the user.
6. **Test end-to-end** – Simulate prompts like "List me appointments for today and tell me the contact number" by driving the
   planner in a unit/integration test. The repository's `tests/` folder contains FastAPI + agent harnesses you can reuse to stub
   responses while you iterate.【F:tests/test_agent_run.py†L1-L94】

Treat this checklist as a living artefact—update it whenever you add new entities or enrich the dispatcher logic so future
contributors know the minimum viable wiring for a multi-step flow.

## 1. Catalogue the MCP tool schemas

Start by cataloguing every data-bearing MCP tool that your agent can reach. QTick already exposes endpoints for the key business objects:

| Object | Primary list tool | Key fields returned |
| --- | --- | --- |
| Appointment | `appointments_list` (FastMCP) / `appointments.list` (REST) | `id`, `customer_name`, `service`, `start_time`, `status`【F:app/mcp_server.py†L13-L48】【F:app/tools/mcp.py†L44-L70】 |
| Invoice | `invoice.list` | `invoice_id`, `customer_name`, `total`, `status`, `items`【F:app/tools/invoice.py†L17-L39】【F:app/services/invoice.py†L51-L71】【F:app/tools/mcp.py†L74-L110】 |
| Lead | `leads.list` | `lead_id`, `name`, `phone`, `email`, `source`【F:app/tools/leads.py†L16-L33】【F:app/tools/mcp.py†L117-L146】 |
| Review | `live_ops.events` summary | Events for review requests triggered by invoice payments, including `customer_name`, `status`, and timestamps【F:app/tools/mcp.py†L147-L198】【F:app/services/live_ops.py†L83-L184】 |

> **Tip:** The MCP server also exposes create/update tools (e.g. `invoice_create`, `invoice.mark_paid`, `leads.create`) that enrich the schema definitions for downstream reasoning.【F:app/mcp_server.py†L50-L90】【F:app/tools/mcp.py†L92-L161】 Even if you only need read-only answers, inspecting these schemas tells the model which attributes exist.

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

The controller below demonstrates how to normalise intents, call the correct tool, and hand the structured rows back to the LLM. It uses a simple dispatcher so the same logic works for invoices, appointments, leads, or reviews:

```python
import asyncio
import json
from contextlib import asynccontextmanager
from datetime import date
from typing import Any, Awaitable, Callable, Dict

from mcp.client.session import ClientSession
from mcp.client.sse import sse_client
from mcp.types import CallToolResult, TextContent


def _date_range_for_today() -> Dict[str, str]:
    today = date.today().isoformat()
    return {"date_from": today, "date_to": today}


ENTITY_TOOL: Dict[str, Dict[str, Any]] = {
    "appointment": {
        "name": "appointments.list",
        "argument_builder": lambda business_id: {
            "business_id": business_id,
            **_date_range_for_today(),
        },
    },
    "invoice": {
        "name": "invoice.list",
        "argument_builder": lambda business_id: {"business_id": business_id},
    },
    "lead": {
        "name": "leads.list",
        "argument_builder": lambda business_id: {"business_id": business_id},
    },
    "review": {
        "name": "live_ops.events",
        "argument_builder": lambda business_id: {
            "business_id": business_id,
            **_date_range_for_today(),
        },
    },
}


def _result_to_payload(result: CallToolResult) -> Any:
    """Prefer structuredContent; fall back to decoded text blocks."""

    if result.structuredContent is not None:
        return result.structuredContent

    text_blocks = [block.text for block in result.content if isinstance(block, TextContent)]
    if not text_blocks:
        return result.model_dump()

    try:
        return json.loads(text_blocks[0])
    except json.JSONDecodeError:
        return text_blocks[0]


async def fetch_entity_rows(
    session: ClientSession, business_id: int, entity: str
) -> Any:
    descriptor = ENTITY_TOOL[entity]
    tool_args = descriptor["argument_builder"](business_id)
    result = await session.call_tool(descriptor["name"], tool_args)
    return _result_to_payload(result)


async def answer_business_question(
    session: ClientSession,
    business_id: int,
    entity: str,
    instruction: str,
    *,
    llm_complete: Callable[[str], Awaitable[str]],
) -> str:
    rows = await fetch_entity_rows(session, business_id, entity)
    summary_prompt = f"""
You are the analyst for today's {entity}s. Follow the instruction strictly.
Instruction: {instruction}
Data: {rows}
Return the result as concise bullet points or tables when appropriate.
"""
    return await llm_complete(summary_prompt)


@asynccontextmanager
async def open_session(base_url: str):
    async with sse_client(base_url) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()
            yield session


async def run():
    async def fake_llm(prompt: str) -> str:
        # Plug in your preferred completion call (OpenAI, Gemini, local model, etc.).
        return f"[LLM would answer based on prompt length {len(prompt)}]"

    async with open_session("http://localhost:8000/sse") as session:
        print(
            await answer_business_question(
                session,
                business_id=42,
                entity="invoice",
                instruction="From today's invoices tell me the highest paid service",
                llm_complete=fake_llm,
            )
        )


asyncio.run(run())
```

Key ideas:

1. **Tool call** – The dispatcher selects the right tool name and arguments based on the entity detected in the user query.
2. **Stateful reasoning** – After receiving the JSON payload, you send the structured result back to the LLM (either as context or through a follow-up prompt) so it can finish the task.
3. **Optional follow-up tools** – If attributes are missing (e.g., appointment rows do not include phone numbers), make an extra call such as `leads.list` before crafting the final answer.

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
