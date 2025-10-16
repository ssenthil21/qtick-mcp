from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.routing import Mount

from app.config import get_settings
from app.dependencies.services import get_java_client_cached

# Import routers directly from submodules
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
from app.health import router as health_router


def configure_logging() -> None:
    """Ensure application logs use the INFO level by default."""
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        )
    else:
        root_logger.setLevel(logging.INFO)

# Configure logging as soon as the module is loaded
configure_logging()

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages application startup and shutdown events.
    """
    # --- Startup Logic ---
    settings = get_settings()
    
    # Log application settings on startup
    settings_snapshot = settings.model_dump(
        by_alias=True,
        exclude={"java_service_token", "google_api_key"},
    )
    logger.info("Application settings on startup: %s", settings_snapshot)

    # Debug check for MCP mount
    has_mcp = any(isinstance(r, Mount) and r.path == "/mcp" for r in app.routes)
    logger.debug("MCP mount present: %s", has_mcp)

    # Initialize shared resources
    client = get_java_client_cached()
    logger.info("Application startup complete.")
    
    try:
        yield  # The application is now running
    finally:
        # --- Shutdown Logic ---
        logger.info("Closing Java client connection.")
        await client.close()
        logger.info("Application shutdown complete.")


# --- Application Setup ---

settings = get_settings()
app = FastAPI(
    title=settings.app_name, 
    lifespan=lifespan, 
    redirect_slashes=False
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:2500", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Include Routers and Mounts ---

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

# Mount the MCP Streamable HTTP server at /mcp
app.mount("/mcp", mcp.streamable_http_app())
#app.mount("/sse", mcp.sse_app()) # Uncomment for local testing with Anthropic MCP client