
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Header, Depends
import os, requests

router = APIRouter()

# ---- Security (optional) ----
def require_api_key(x_api_key: Optional[str] = Header(None)):
    expected = os.getenv("QTF_API_KEY")
    if expected and x_api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return True

# ---- MCP Tool Catalog ----
TOOLS: List[Dict[str, Any]] = [
    {
        "name": "appointments.book",
        "description": "Book an appointment in QTick.",
        "input_schema": {
            "type": "object",
            "properties": {
                "business_id": {"type":"string"},
                "customer_name": {"type":"string"},
                "service_id": {"type":"string"},
                "datetime": {"type":"string","format":"date-time"}
            },
            "required": ["business_id","customer_name","service_id","datetime"]
        },
    },
    {
        "name": "appointments.list",
        "description": "List appointments for a business with optional date range/status/pagination.",
        "input_schema": {
            "type": "object",
            "properties": {
                "business_id":{"type":"string"},
                "date_from":{"type":"string","format":"date"},
                "date_to":{"type":"string","format":"date"},
                "status":{"type":"string","enum":["open","confirmed","completed","cancelled","no_show","pending"]},
                "page":{"type":"integer","minimum":1,"default":1},
                "page_size":{"type":"integer","minimum":1,"maximum":100,"default":20}
            },
            "required": ["business_id"]
        },
    },
    {
        "name": "invoice.create",
        "description": "Create an invoice with line items.",
        "input_schema": {
            "type": "object",
            "properties": {
                "business_id":{"type":"string"},
                "customer_name":{"type":"string"},
                "items":{"type":"array","items":{
                    "type":"object",
                    "properties":{
                        "item_id":{"type":"string"},
                        "description":{"type":"string"},
                        "quantity":{"type":"integer","minimum":1},
                        "unit_price":{"type":"number"},
                        "price":{"type":"number","description":"alias for unit_price"},
                        "tax_rate":{"type":"number","default":0}
                    },
                    "required":["description","quantity"]
                }},
                "currency":{"type":"string","default":"SGD"},
                "appointment_id":{"type":"string"},
                "notes":{"type":"string"}
            },
            "required": ["business_id","customer_name","items"]
        },
    },
    {
        "name": "leads.create",
        "description": "Create a new customer lead.",
        "input_schema": {
            "type": "object",
            "properties": {
                "business_id":{"type":"string"},
                "name":{"type":"string"},
                "phone":{"type":"string"},
                "email":{"type":"string","format":"email"},
                "source":{"type":"string","default":"manual"},
                "notes":{"type":"string"}
            },
            "required": ["business_id","name"]
        },
    },
    {
        "name": "campaign.send_whatsapp",
        "description": "Send a WhatsApp campaign message to a customer.",
        "input_schema": {
            "type":"object",
            "properties":{
                "customer_name":{"type":"string"},
                "phone_number":{"type":"string"},
                "message_template":{"type":"string"},
                "offer_code":{"type":"string"},
                "expiry":{"type":"string"}
            },
            "required":["customer_name","phone_number","message_template"]
        },
    },
    {
        "name": "analytics.report",
        "description": "Fetch analytics for a business over a period.",
        "input_schema": {
            "type":"object",
            "properties":{
                "business_id":{"type":"string"},
                "metrics":{"type":"array","items":{"type":"string"}},
                "period":{"type":"string"}
            },
            "required":["business_id","metrics","period"]
        },
    },
]

@router.get("/tools/list", dependencies=[Depends(require_api_key)])
def mcp_tools_list():
    return {"tools": TOOLS}

# ---- Invocation ----
from pydantic import BaseModel, Field

class ToolCall(BaseModel):
    name: str = Field(..., description="Tool name from /tools/list")
    arguments: Dict[str, Any] = Field(default_factory=dict)

def _self_base() -> str:
    # Allow override by env; default to local if unset
    # On Render, this should be the PUBLIC base (e.g., https://your.onrender.com)
    return os.getenv("MCP_PUBLIC_BASE", "http://127.0.0.1:8000")

@router.post("/tools/call", dependencies=[Depends(require_api_key)])
def mcp_tools_call(call: ToolCall):
    base = _self_base()
    try:
        # Route by tool name; forward to existing REST endpoints
        if call.name == "appointments.book":
            url = f"{base}/tools/appointment/book"
            resp = requests.post(url, json=call.arguments, timeout=30)
            resp.raise_for_status()
            return resp.json()

        if call.name == "appointments.list":
            url = f"{base}/tools/appointment/list"
            resp = requests.post(url, json=call.arguments, timeout=30)
            resp.raise_for_status()
            return resp.json()

        if call.name == "invoice.create":
            url = f"{base}/tools/invoice/create"
            resp = requests.post(url, json=call.arguments, timeout=30)
            resp.raise_for_status()
            return resp.json()

        if call.name == "leads.create":
            url = f"{base}/tools/leads/create"
            resp = requests.post(url, json=call.arguments, timeout=30)
            resp.raise_for_status()
            return resp.json()

        if call.name == "campaign.send_whatsapp":
            url = f"{base}/tools/campaign/sendWhatsApp"
            resp = requests.post(url, json=call.arguments, timeout=30)
            resp.raise_for_status()
            return resp.json()

        if call.name == "analytics.report":
            url = f"{base}/tools/analytics/report"
            resp = requests.post(url, json=call.arguments, timeout=30)
            resp.raise_for_status()
            return resp.json()

        raise HTTPException(status_code=404, detail=f"Unknown tool: {call.name}")
    except requests.HTTPError as e:
        # bubble up the underlying service error
        status = e.response.status_code if e.response is not None else 500
        detail = e.response.text if e.response is not None else str(e)
        raise HTTPException(status_code=status, detail=detail)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
