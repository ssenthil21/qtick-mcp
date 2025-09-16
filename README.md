
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
