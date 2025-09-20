# app/main.py
from __future__ import annotations

import os
from typing import Callable, Awaitable, Dict, Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.routing import Mount

# -----------------------------------------------------------------------------
# Settings (safe defaults if app/config.py doesn't export `settings`)
# -----------------------------------------------------------------------------
try:
    from app.config import settings  # must export a variable named `settings`
except Exception:
    class _Defaults:
        app_name = "QTick API"
        cors_allow_origins = "*"
    settings = _Defaults()

# -----------------------------------------------------------------------------
# Lifespan (optional)
# -----------------------------------------------------------------------------
try:
    from app.lifecycle import lifespan
except Exception:
    lifespan = None  # FastAPI accepts None

# -----------------------------------------------------------------------------
# MCP server (required)
# -----------------------------------------------------------------------------
try:
    from app.mcp_server import mcp
except Exception as e:
    raise RuntimeError(f"Failed to import MCP server (app.mcp_server): {e}")

# -----------------------------------------------------------------------------
# Optional routers (health/debug/your REST)
# -----------------------------------------------------------------------------
try:
    from app.health import router as health_router     # /mcp/info, /mcp/health
except Exception:
    health_router = None

try:
    from app.debug_routes import router as debug_router  # /_debug/routes
except Exception:
    debug_router = None

tool_routers = []
for modpath, attr in [
    ("app.tools.appointment", "router"),
    ("app.tools.campaign", "router"),
    ("app.tools.analytics", "router"),
    ("app.tools.invoice", "router"),
    ("app.tools.leads", "router"),
    ("app.tools.agent", "router"),
]:
    try:
        module = __import__(modpath, fromlist=[attr])
        tool_routers.append(getattr(module, attr))
    except Exception:
        pass

# -----------------------------------------------------------------------------
# Wrapper: map ONLY inner "/" -> "/mcp" (or "/sse") for older SDKs
# Leaves other inner paths (e.g., "/messages") untouched.
# -----------------------------------------------------------------------------
class MapRootToPrefixASGI:
    """
    Wrap an ASGI app so that only a root path '/' is rewritten to the given prefix.
    Fixes old MCP SDKs that expect '/mcp' (streamable HTTP) and '/sse' (SSE)
    while leaving inner paths like '/messages' untouched.
    """
    def __init__(self, app, prefix: str):
        self.app = app
        self.prefix = "/" + prefix.strip("/")  # '/mcp' or '/sse'

    async def __call__(self, scope: Dict[str, Any], receive: Callable[..., Awaitable], send: Callable[..., Awaitable]):
        if scope.get("type") in ("http", "websocket"):
            path = scope.get("path", "/") or "/"
            # After Mount('/mcp', ...), an outer '/mcp' arrives as inner '/'
            if path == "/":
                scope = dict(scope)
                scope["path"] = self.prefix
        return await self.app(scope, receive, send)

# -----------------------------------------------------------------------------
# FastAPI app
# -----------------------------------------------------------------------------
app = FastAPI(
    title=getattr(settings, "app_name", "QTick API"),
    lifespan=lifespan,
    # important: avoid /mcp -> /mcp/ redirects (breaks POST handshake)
    redirect_slashes=False,
)

# CORS for your REST APIs (MCP is server-to-server; CORS not needed there)
allow_origins = getattr(settings, "cors_allow_origins", "*")
app.add_middleware(
    CORSMiddleware,
    #allow_origins=allow_origins.split(",") if isinstance(allow_origins, str) else ["*"],
    allow_origins=["http://localhost:2500"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include optional routers
if health_router:
    app.include_router(health_router)   # /mcp/info, /mcp/health
if debug_router:
    app.include_router(debug_router)    # /_debug/routes
for r in tool_routers:
    app.include_router(r)

# -----------------------------------------------------------------------------
# Mount MCP transports (supports both new & old MCP SDKs)
# -----------------------------------------------------------------------------
def _mount_mcp_transports(_app: FastAPI) -> None:
    # ---------- Streamable HTTP ----------
    if hasattr(mcp, "streamable_http_app"):
        try:
            # Newer SDKs support specifying path="/"
            http_inner = mcp.streamable_http_app(path="/")
            _app.mount("/mcp", http_inner)
        except TypeError:
            # Older SDKs: inner app expects '/mcp'
            http_inner = mcp.streamable_http_app()
            _app.mount("/mcp", MapRootToPrefixASGI(http_inner, "/mcp"))
    elif hasattr(mcp, "streaming_http_app"):
        try:
            http_inner = mcp.streaming_http_app(path="/")
            _app.mount("/mcp", http_inner)
        except TypeError:
            http_inner = mcp.streaming_http_app()
            _app.mount("/mcp", MapRootToPrefixASGI(http_inner, "/mcp"))
    else:
        raise RuntimeError("MCP SDK lacks HTTP transport. Install/upgrade: pip install -U 'mcp[cli]'")

    # ---------- SSE (optional for local tests) ----------
    if hasattr(mcp, "sse_app"):
        try:
            sse_inner = mcp.sse_app(path="/")
            _app.mount("/sse", sse_inner)
        except TypeError:
            sse_inner = mcp.sse_app()
            # Only map '/' -> '/sse'; do NOT rewrite '/messages'
            _app.mount("/sse", MapRootToPrefixASGI(sse_inner, "/sse"))

_mount_mcp_transports(app)

# -----------------------------------------------------------------------------
# Startup debug: print mounts so you can confirm /mcp & /sse are present
# -----------------------------------------------------------------------------
@app.on_event("startup")
async def _debug_mounts() -> None:
    print("[DEBUG] Mounted routes:")
    for route in app.routes:
        if isinstance(route, Mount):
            children = getattr(route.app, "routes", []) or []
            child_paths = [getattr(cr, "path", None) for cr in children]
            print(f"  - MOUNT {route.path} (children: {child_paths})")

# Simple root for sanity
@app.get("/")
def root_info():
    return {"name": getattr(settings, "app_name", "QTick API"), "status": "ok"}

# Allow `python -m uvicorn app.main:app --reload`
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8000")),
        reload=bool(int(os.getenv("RELOAD", "0"))),
        log_level=os.getenv("LOG_LEVEL", "info"),
    )
