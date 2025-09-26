
# QTick MCP Service (Full, Consolidated)

## Windows 10 Quickstart

1. **Boot the API**
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

2. **Pick an MCP transport** – The repo includes ready-made harnesses that wire
   up `mcp.client.session.ClientSession` with either JSON-RPC over stdio or
   server-sent events (SSE):
   - `TEST_mcp_client.py` – stdio transport for local subprocess connectivity.
   - `TEST_mcp_client_stream.py` – streaming JSON transport over TCP.
   - `TEST_mcp_client_sse.py` – SSE harness that connects to
     `http://127.0.0.1:8000/sse`.

   Each script exposes a minimal checklist: initialise the session, list the
   advertised tools, and make a sample `ping` call. Copy one of them when
   bootstrapping your own client to ensure you configure the right
   `ClientSession` transport and headers.

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

### Agent LLM configuration

The agent runtime is standardised on Google Gemini. Configure it with the following knobs:

| Setting | Description | Default |
| --- | --- | --- |
| `QTICK_AGENT_GOOGLE_MODEL` | Gemini model name used by the agent. | `gemini-1.5-flash` |
| `QTICK_AGENT_TEMPERATURE` | Sampling temperature applied to the Gemini model. | `0.0` |
| `QTICK_GOOGLE_API_KEY` | Server-side Gemini API key (fallbacks to `GOOGLE_API_KEY`). | – |

When `QTICK_GOOGLE_API_KEY` is set the value is copied into `GOOGLE_API_KEY` so LangChain and
other downstream clients inherit the same credential automatically.

The `/agent/run` endpoint accepts either a single string prompt or a multi-part prompt payload
(lists of strings and/or `{role, content}` dictionaries). The server flattens these segments
into a single Gemini-friendly string before dispatching the request, so you can stream complex
conversation context without changing the API contract.

If imports act weird after overwriting files, clear caches:
```bat
rmdir /S /Q app\__pycache__
rmdir /S /Q app\tools\__pycache__
rmdir /S /Q app\schemas\__pycache__
rmdir /S /Q langchain_tools\__pycache__
```
