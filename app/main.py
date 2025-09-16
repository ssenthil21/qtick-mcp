
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import routers directly from submodules (safer under reload)
from app.tools.appointment import router as appointment_router
from app.tools.campaign import router as campaign_router
from app.tools.analytics import router as analytics_router
from app.tools.invoice import router as invoice_router
from app.tools.leads import router as leads_router
from app.tools.agent import router as agent_router

app = FastAPI(title="QTick MCP Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5500", "http://127.0.0.1:5500"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(appointment_router, prefix="/tools/appointment")
app.include_router(campaign_router, prefix="/tools/campaign")
app.include_router(analytics_router, prefix="/tools/analytics")
app.include_router(invoice_router, prefix="/tools/invoice")
app.include_router(leads_router, prefix="/tools/leads")
app.include_router(agent_router, prefix="/agent")
