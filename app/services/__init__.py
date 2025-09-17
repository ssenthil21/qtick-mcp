"""Service package public API definitions.

This module previously imported each service implementation eagerly at
import-time. When the HTTP client attempted to import
``app.services.exceptions`` the interpreter first executed this module, which
in turn imported the service implementations. Those implementations depend on
``app.clients.java`` and therefore triggered a circular import during
application start up. To avoid that situation we lazily import the service
implementations only when they are accessed.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

__all__ = [
    "AppointmentService",
    "AnalyticsService",
    "CampaignService",
    "InvoiceService",
    "LeadService",
]

_SERVICE_MODULES = {
    "AppointmentService": "appointment",
    "AnalyticsService": "analytics",
    "CampaignService": "campaign",
    "InvoiceService": "invoice",
    "LeadService": "leads",
}


def __getattr__(name: str) -> Any:
    if name not in _SERVICE_MODULES:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module = import_module(f".{_SERVICE_MODULES[name]}", __name__)
    attr = getattr(module, name)
    globals()[name] = attr
    return attr


if TYPE_CHECKING:  # pragma: no cover - import for static analysis only
    from .analytics import AnalyticsService as AnalyticsService
    from .appointment import AppointmentService as AppointmentService
    from .campaign import CampaignService as CampaignService
    from .invoice import InvoiceService as InvoiceService
    from .leads import LeadService as LeadService

