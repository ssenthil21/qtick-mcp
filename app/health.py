# app/health.py
from fastapi import APIRouter
router = APIRouter()

@router.get("/mcp/info")
def mcp_info():
    return {"status":"ok","transport":"streamable-http","path":"/mcp"}

@router.get("/mcp/health")
def mcp_health():
    return {"ok": True}
