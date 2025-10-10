
# QTick MCP Service (Full, Consolidated)

## Windows 10 Quickstart
```bat
cd C:\projects\qtick_mcp_full
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open Swagger at http://127.0.0.1:8000/docs and try:
- POST /tools/appointment/book
- POST /tools/appointment/list
- POST /tools/invoice/create
- POST /tools/leads/create
- POST /tools/campaign/sendWhatsApp
- POST /tools/analytics/report

## Lead creation Java API example

When running against the real Java services you must authorise requests with the
bearer token configured for your environment. Export the token so both the
FastAPI service and command-line utilities can reuse it:

```bash
export QTICK_USE_MOCK_DATA=0
export QTICK_JAVA_SERVICE_TOKEN=YOUR_BEARER_TOKEN
FOLLOW_UP_TS=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
```

The payload used by the `/tools/leads/create` MCP tool matches the downstream
Java endpoint. You can inspect or debug the live flow with a direct `curl`
request:

```bash
curl -X POST "https://api.qa.qtick.co/api/biz/sales-enq" \
  -H "Authorization: Bearer ${QTICK_JAVA_SERVICE_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{
    \"bizId\": \"<tool selection id>\",
    \"phone\": \"<input from nlp>\",
    \"custName\": \"<input from nlp>\",
    \"location\": \"<input from nlp>\",
    \"enqFor\": \"<input from nlp>\",
    \"srcChannel\": \"WA\",
    \"campId\": null,
    \"campName\": null,
    \"details\": \"<input from nlp>\",
    \"thdStatus\": \"O\",
    \"interest\": 4,
    \"followUpDate\": \"${FOLLOW_UP_TS}\",
    \"enquiredOn\": \"${FOLLOW_UP_TS}\",
    \"enqForTime\": \"${FOLLOW_UP_TS}\",
    \"attnStaffId\": 21,
    \"attnChannel\": \"P\"
  }"
```

> Replace the placeholder values with the actual data captured from the LLM or
> client workflow. The `FOLLOW_UP_TS` helper above captures the current UTC
> timestamp; feel free to adjust the value if the follow-up needs to happen in
> the future.

To inspect leads that have already been captured for a business, call the list
endpoint with the same bearer token. The query parameters mirror the defaults
used by the MCP tool, so you can leave them empty to retrieve the full list:

```bash
curl "https://api.qa.qtick.co/api/biz/<bizId>/sales-enq/list?searchText=&status=&periodType=&periodFilterBy=A&fromDate=&toDate=" \
  -H "Authorization: Bearer ${QTICK_JAVA_SERVICE_TOKEN}"
```

## Multi-step tool reasoning

Need an agent to call multiple tools and stitch the answers together (e.g. "List today's appointments and share their phone numbers")? See [`docs/multi_step_tool_workflow.md`](docs/multi_step_tool_workflow.md) for a walkthrough on prompting, orchestrating MCP calls, and feeding the structured results back into the LLM.

## Test with Gemini (LangChain Structured Agent)
New terminal:
```bat
cd C:\projects\qtick_mcp_full
venv\Scripts\activate
set GOOGLE_API_KEY=YOUR_MAKERSUITE_API_KEY
python test_agent_gemini.py
```

If imports act weird after overwriting files, clear caches:
```bat
rmdir /S /Q app\__pycache__
rmdir /S /Q app\tools\__pycache__
rmdir /S /Q app\schemas\__pycache__
rmdir /S /Q langchain_tools\__pycache__
```

## Pre-merge smoke test

Before merging changes that touch the agent service, run the automated smoke
test locally to confirm that the configured Gemini model is reachable and the
FastAPI endpoint responds correctly:

> The service defaults to `gemini-2.5-flash`. Override it by exporting
> `QTICK_AGENT_GOOGLE_MODEL` if you need to target a different release.

```bash
export QTICK_GOOGLE_API_KEY=YOUR_MAKERSUITE_API_KEY
python scripts/agent_smoke_test.py
```

You can override the default prompt or timeout if needed:

```bash
python scripts/agent_smoke_test.py --prompt "Say hello" --timeout 90
```

For CI-style checks without calling external services, continue to rely on the
unit test suite:

```bash
pytest
```
