"""Routes for browsing mock data stored by the in-memory repositories."""
from __future__ import annotations

import html
import json
from typing import Any, Dict, Iterable, List, Mapping

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from app.services.mock_store import BusinessRecord, ServiceRecord, get_mock_store

router = APIRouter()


def _stringify(value: Any) -> str:
    """Return a JSON-friendly string representation for table cells."""
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return str(value)
    return json.dumps(value, default=str)


def _build_table(title: str, rows: Iterable[Mapping[str, Any]]) -> str:
    row_list: List[Dict[str, Any]] = [dict(row) for row in rows]
    section_parts = [f"<section><h2>{html.escape(title)}</h2>"]
    if not row_list:
        section_parts.append("<p>No records found.</p></section>")
        return "".join(section_parts)

    columns: List[str] = []
    for row in row_list:
        for key in row.keys():
            if key not in columns:
                columns.append(key)

    header = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
    body_rows: List[str] = []
    for row in row_list:
        cells = []
        for column in columns:
            value = _stringify(row.get(column))
            cells.append(f"<td>{html.escape(value)}</td>")
        body_rows.append("<tr>" + "".join(cells) + "</tr>")
    table_html = (
        "<table><thead><tr>"
        + header
        + "</tr></thead><tbody>"
        + "".join(body_rows)
        + "</tbody></table>"
    )
    section_parts.append(table_html)
    section_parts.append("</section>")
    return "".join(section_parts)


def _business_rows(businesses: Iterable[BusinessRecord]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for business in businesses:
        rows.append(
            {
                "business_id": business.business_id,
                "name": business.name,
                "location": business.location,
                "tags": list(business.tags),
            }
        )
    return rows


def _service_rows(businesses: Iterable[BusinessRecord]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for business in businesses:
        for service in business.services:
            rows.append(_service_to_row(business.business_id, service))
    return rows


def _service_to_row(business_id: int, service: ServiceRecord) -> Dict[str, Any]:
    return {
        "business_id": business_id,
        "service_id": service.service_id,
        "name": service.name,
        "category": service.category,
        "duration_minutes": service.duration_minutes,
        "price": service.price,
    }


@router.get("/mock-data", response_class=HTMLResponse)
async def view_mock_data() -> HTMLResponse:
    """Render all mock data from the shared in-memory store as HTML tables."""
    store = get_mock_store()

    businesses = list(store.master_data.iter_businesses())
    sections = [
        _build_table("Businesses", _business_rows(businesses)),
        _build_table("Services", _service_rows(businesses)),
        _build_table("Appointments", store.appointments._appointments.values()),
        _build_table("Invoices", store.invoices._invoices.values()),
        _build_table("Leads", store.leads._leads.values()),
        _build_table("Campaigns", store.campaigns._campaigns.values()),
    ]

    sections_html = "".join(sections)
    html_content = f"""
    <html>
        <head>
            <title>Mock Data Overview</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 2rem; }}
                h1 {{ text-align: center; }}
                section {{ margin-bottom: 2rem; }}
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ border: 1px solid #ccc; padding: 0.5rem; text-align: left; }}
                th {{ background-color: #f0f0f0; }}
                tbody tr:nth-child(even) {{ background-color: #fafafa; }}
            </style>
        </head>
        <body>
            <h1>Mock Data Overview</h1>
            {sections_html}
        </body>
    </html>
    """

    return HTMLResponse(content=html_content)


@router.delete("/mock-data/{collection}/{record_id}")
async def delete_mock_record(collection: str, record_id: str) -> Dict[str, str]:
    """Remove a record from one of the mock data repositories."""

    store = get_mock_store()
    normalized = collection.strip().lower()

    collection_map = {
        "appointment": ("appointments", store.appointments.delete),
        "appointments": ("appointments", store.appointments.delete),
        "invoice": ("invoices", store.invoices.delete),
        "invoices": ("invoices", store.invoices.delete),
        "lead": ("leads", store.leads.delete),
        "leads": ("leads", store.leads.delete),
        "campaign": ("campaigns", store.campaigns.delete),
        "campaigns": ("campaigns", store.campaigns.delete),
    }

    mapping = collection_map.get(normalized)
    if not mapping:
        raise HTTPException(status_code=404, detail="Unsupported mock data collection")

    canonical_name, delete_fn = mapping
    deleted = await delete_fn(record_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Record not found")

    return {"status": "deleted", "collection": canonical_name, "record_id": record_id}
