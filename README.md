
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
