# app/debug_routes.py
from fastapi import APIRouter
from starlette.routing import Mount

router = APIRouter()

@router.get("/_debug/routes")
def list_routes():
    from app.main import app
    data = []
    for r in app.routes:
        if isinstance(r, Mount):
            entry = {"type": "mount", "path": r.path, "app": getattr(r.app, "__class__", type(r.app)).__name__}
            # Try to introspect child routes
            try:
                entry["child_routes"] = [getattr(cr, "path", None) for cr in getattr(r.app, "routes", [])]
            except Exception:
                entry["child_routes"] = None
            data.append(entry)
        else:
            methods = getattr(r, "methods", None)
            path = getattr(r, "path", getattr(r, "path_regex", None))
            data.append({"type": "route", "path": path, "methods": list(methods) if methods else None})
    return data
