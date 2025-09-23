
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.dependencies.services import get_java_client_cached

# Import routers directly from submodules (safer under reload)
from app.mock_data_view import router as mock_data_router
from app.tools.analytics import router as analytics_router
from app.tools.agent import router as agent_router
from app.tools.appointment import router as appointment_router
from app.tools.business import router as business_router
from app.tools.campaign import router as campaign_router
from app.tools.invoice import router as invoice_router
from app.tools.leads import router as leads_router
from app.tools.live_ops import router as live_ops_router
from app.tools.mcp import router as mcp_router
from app.mcp_server import mcp
from starlette.routing import Mount
from app.health import router as health_router 



@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    client = get_java_client_cached()
    try:
        yield
    finally:
        await client.close()


settings = get_settings()
app = FastAPI(title=settings.app_name, lifespan=lifespan,redirect_slashes=False)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:2500","*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(appointment_router, prefix="/tools/appointment")
app.include_router(business_router, prefix="/tools/business")
app.include_router(campaign_router, prefix="/tools/campaign")
app.include_router(analytics_router, prefix="/tools/analytics")
app.include_router(invoice_router, prefix="/tools/invoice")
app.include_router(leads_router, prefix="/tools/leads")
app.include_router(live_ops_router, prefix="/tools/live-ops")
app.include_router(agent_router, prefix="/agent")
app.include_router(mcp_router)  # Exposes /tools/list and /tools/call
app.include_router(health_router)
app.include_router(mock_data_router)
app.mount("/mcp", mcp.streamable_http_app()) # Mount the MCP Streamable HTTP server at /mcp
#app.mount("/sse", mcp.sse_app()) # add this line for local testing with the Anthropic MCP client:

from starlette.routing import Mount
@app.on_event("startup")
async def _debug_routes():
    has_mcp = any(isinstance(r, Mount) and r.path == "/mcp" for r in app.routes)
    print(f"[DEBUG] MCP mount present: {has_mcp}")
