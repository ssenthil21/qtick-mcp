
# app/tools/mcp.py
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Header, Depends
import os, requests
from pydantic import BaseModel, Field

router = APIRouter()

def require_api_key(x_api_key: Optional[str] = Header(None)):
    expected = os.getenv("QTF_API_KEY")
    if expected and x_api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return True

TOOLS: List[Dict[str, Any]] = [
    {
        "name": "business.search",
        "description": "Search for businesses by name, id, or tag.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 25, "default": 10},
            },
            "required": ["query"],
        },
    },
    {
        "name": "business.services.find",
        "description": "Find service identifiers for a business using name keywords.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "service_name": {"type": "string"},
                "business_id": {"type": "integer"},
                "business_name": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 20, "default": 5},
            },
            "required": ["service_name"],
        },
    },
    {
        "name": "appointments.book",
        "description": "Book an appointment in QTick.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "business_id": {"type": "integer"},
                "customer_name": {"type":"string"},
                "service_id": {"type":"integer"},
                "datetime": {"type":"string","format":"date-time"}
            },
            "required": ["business_id","customer_name","service_id","datetime"]
        },
    },
    {
        "name": "appointments.list",
        "description": "List appointments for a business with optional date range/status/pagination.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "business_id": {"type": "integer"},
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
        "inputSchema": {
            "type": "object",
            "properties": {
                "business_id": {"type": "integer"},
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
        "name": "invoice.list",
        "description": "List invoices for a business.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "business_id": {"type": "integer"},
            },
            "required": ["business_id"],
        },
    },
    {
        "name": "leads.create",
        "description": "Create a new customer lead.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "business_id": {"type": "integer"},
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
        "name": "leads.list",
        "description": "List leads captured for a business.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "business_id": {"type": "integer"},
            },
            "required": ["business_id"],
        },
    },
    {
        "name": "campaign.send_whatsapp",
        "description": "Send a WhatsApp campaign message to a customer.",
        "inputSchema": {
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
        "inputSchema": {
            "type":"object",
            "properties":{
                "business_id": {"type": "integer"},
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

class ToolCall(BaseModel):
    name: str = Field(..., description="Tool name from /tools/list")
    arguments: Dict[str, Any] = Field(default_factory=dict)

def _self_base() -> str:
    return os.getenv("MCP_PUBLIC_BASE", "http://127.0.0.1:8000")

@router.post("/tools/call", dependencies=[Depends(require_api_key)])
def mcp_tools_call(call: ToolCall):
    base = _self_base()
    try:
        routes = {
            "business.search": "/tools/business/search",
            "business.services.find": "/tools/business/services/find",
            "appointments.book": "/tools/appointment/book",
            "appointments.list": "/tools/appointment/list",
            "invoice.create": "/tools/invoice/create",
            "invoice.list": "/tools/invoice/list",
            "leads.create": "/tools/leads/create",
            "leads.list": "/tools/leads/list",
            "campaign.send_whatsapp": "/tools/campaign/sendWhatsApp",
            "analytics.report": "/tools/analytics/report",
        }
        if call.name not in routes:
            raise HTTPException(status_code=404, detail=f"Unknown tool: {call.name}")
        url = f"{base}{routes[call.name]}"
        headers = {"X-API-Key": os.getenv("QTF_API_KEY")} if os.getenv("QTF_API_KEY") else None
        resp = requests.post(url, json=call.arguments, timeout=30, headers=headers)
        resp.raise_for_status()
        return resp.json()
    except requests.HTTPError as e:
        status = e.response.status_code if e.response is not None else 500
        detail = e.response.text if e.response is not None else str(e)
        raise HTTPException(status_code=status, detail=detail)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
