# app/main.py
from __future__ import annotations

import os
import logging
from typing import Callable, Awaitable, Dict, Any, List, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.routing import Mount

# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
    force=True,
)
for name in [
    "uvicorn", "uvicorn.error", "uvicorn.access",
    "starlette", "fastapi",
    "mcp", "mcp.server", "mcp.client", "mcp.shared",
    "httpx", "anyio",
]:
    logging.getLogger(name).setLevel(logging.DEBUG)
log = logging.getLogger("qtick.server")

# -----------------------------------------------------------------------------
# Settings / lifespan (optional)
# -----------------------------------------------------------------------------
try:
    from app.config import settings
except Exception:
    class _Defaults:
        app_name = "QTick API"
        cors_allow_origins = "*"
    settings = _Defaults()

try:
    from app.lifecycle import lifespan
except Exception:
    lifespan = None

# -----------------------------------------------------------------------------
# MCP server (required)
# -----------------------------------------------------------------------------
try:
    from app.mcp_server import mcp
except Exception as e:
    raise RuntimeError(f"Failed to import MCP server (app.mcp_server): {e}")

# Optional routers
try:
    from app.health import router as health_router  # /mcp/info, /mcp/health
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
# ASGI wrapper that tries multiple inner paths if one returns 404
# -----------------------------------------------------------------------------
class MultiPathASGI:
    """
    For mounted sub-apps where the inner app might expect '/' OR '/mcp',
    try both and return the first non-404 response.

    This buffers the request body to allow re-trying. It only rewrites the
    path when the inner path is '/' (as seen by the mounted sub-app).
    """
    def __init__(self, inner_app, candidate_paths: List[str]):
        self.inner = inner_app
        # Ensure candidates are absolute paths, unique, preserve order
        seen = set()
        self.candidates = []
        for p in candidate_paths:
            p = "/" + p.strip("/")
            if p not in seen:
                self.candidates.append(p)
                seen.add(p)

    async def __call__(self, scope: Dict[str, Any], receive: Callable, send: Callable):
        if scope.get("type") not in ("http", "websocket"):
            return await self.inner(scope, receive, send)

        path = scope.get("path", "/") or "/"
        method = scope.get("method", "GET")
        # Only do the multi-try when the mounted path stripped us to '/'
        if path != "/":
            return await self.inner(scope, receive, send)

        # Buffer request body so we can replay to inner app
        body_chunks: List[bytes] = []
        more_body_flags: List[bool] = []

        async def drain_receive():
            nonlocal body_chunks, more_body_flags
            while True:
                message = await receive()
                if message["type"] != "http.request":
                    # e.g. http.disconnect
                    body_chunks.append(b"")
                    more_body_flags.append(False)
                    return message
                body_chunks.append(message.get("body", b""))
                more = bool(message.get("more_body", False))
                more_body_flags.append(more)
                if not more:
                    break
            return None

        # Drain the body once
        disconnect_msg = await drain_receive()

        async def make_recv():
            # replay buffered events once, then return empty events
            sent = {"i": 0, "done": False}

            async def _recv():
                if not sent["done"]:
                    i = sent["i"]
                    if i < len(body_chunks):
                        msg = {
                            "type": "http.request",
                            "body": body_chunks[i],
                            "more_body": more_body_flags[i],
                        }
                        sent["i"] = i + 1
                        if not more_body_flags[i]:
                            sent["done"] = True
                        return msg
                    else:
                        sent["done"] = True
                        return {"type": "http.request", "body": b"", "more_body": False}
                # After we replay, if inner still asks:
                return {"type": "http.request", "body": b"", "more_body": False}

            return _recv

        # If client disconnected during read, short-circuit
        if disconnect_msg and disconnect_msg.get("type") == "http.disconnect":
            return await send({"type": "http.response.start", "status": 499, "headers": []})

        # Try each candidate path until one is not 404
        for candidate in self.candidates:
            scope_try = dict(scope)
            scope_try["path"] = candidate

            # Capture inner response
            status_code_holder: Dict[str, Optional[int]] = {"status": None}
            buffered_events: List[Dict[str, Any]] = []

            async def send_buffered(event: Dict[str, Any]):
                # First start captures status
                if event["type"] == "http.response.start":
                    status_code_holder["status"] = event.get("status", 200)
                buffered_events.append(event)

            # Run inner
            recv_try = await make_recv()
            await self.inner(scope_try, recv_try, send_buffered)

            if status_code_holder["status"] != 404:
                # Flush buffered events to outer send
                for ev in buffered_events:
                    await send(ev)
                return

            # else try next candidate

        # If all candidates failed, return 404
        return await send(
            {"type": "http.response.start", "status": 404, "headers": [(b"content-type", b"application/json")]}
        ) or await send({"type": "http.response.body", "body": b'{"detail":"Not Found"}', "more_body": False})


# -----------------------------------------------------------------------------
# FastAPI app
# -----------------------------------------------------------------------------
app = FastAPI(
    title=getattr(settings, "app_name", "QTick API"),
    lifespan=lifespan,
    redirect_slashes=False,  # important for POST /mcp
)

allow_origins = getattr(settings, "cors_allow_origins", "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins.split(",") if isinstance(allow_origins, str) else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def _log_requests(request, call_next):
    log.debug("REQ %s %s", request.method, request.url.path)
    try:
        response = await call_next(request)
        log.debug("RES %s %s -> %s", request.method, request.url.path, response.status_code)
        return response
    except Exception:
        log.exception("Unhandled exception while handling %s %s", request.method, request.url.path)
        raise

# Optional routers
if health_router:
    app.include_router(health_router)
if debug_router:
    app.include_router(debug_router)
for r in tool_routers:
    app.include_router(r)

# -----------------------------------------------------------------------------
# Mount MCP transports (always wrap with MultiPathASGI over ['/', '/mcp'])
# -----------------------------------------------------------------------------
def _mount_mcp_transports(_app: FastAPI) -> None:
    # Streamable HTTP
    if hasattr(mcp, "streamable_http_app"):
        http_inner = mcp.streamable_http_app()
    elif hasattr(mcp, "streaming_http_app"):
        http_inner = mcp.streaming_http_app()
    else:
        raise RuntimeError("MCP SDK lacks HTTP transport. pip install -U 'mcp[cli]'")

    _app.mount("/mcp", MultiPathASGI(http_inner, candidate_paths=["/", "/mcp"]))

    # SSE (optional)
    if hasattr(mcp, "sse_app"):
        sse_inner = mcp.sse_app()
        _app.mount("/sse", MultiPathASGI(sse_inner, candidate_paths=["/messages/", "/"]))

_mount_mcp_transports(app)

# -----------------------------------------------------------------------------
# Startup: print mounts
# -----------------------------------------------------------------------------
@app.on_event("startup")
async def _debug_mounts() -> None:
    print("[DEBUG] Mounted routes:")
    for route in app.routes:
        if isinstance(route, Mount):
            children = getattr(route.app, "routes", []) or []
            child_paths = [getattr(cr, "path", None) for cr in children]
            print(f"  - MOUNT {route.path} (children: {child_paths})")

@app.get("/")
def root_info():
    return {"name": getattr(settings, "app_name", "QTick API"), "status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8000")),
        reload=bool(int(os.getenv("RELOAD", "0"))),
        log_level=os.getenv("LOG_LEVEL", "debug"),
    )
