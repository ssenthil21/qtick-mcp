from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Optional, Protocol

from google.api_core.exceptions import GoogleAPIError
import google.generativeai as genai

from app.clients.java import JavaServiceClient
from app.schemas.analytics import AnalyticsRequest, AnalyticsResponse
from app.schemas.business import BusinessSummary
from app.schemas.daily_summary import (
    DailySummaryData,
    DailySummaryMetric,
    DailySummaryRequest,
    DailySummaryResponse,
)
from app.services.exceptions import ServiceError
from app.services.mock_store import (
    AnalyticsRepository,
    MasterDataRepository,
    get_mock_store,
)

logger = logging.getLogger(__name__)

_DEFAULT_METRICS = ["footfall", "revenue", "leads"]


class DailySummaryGenerator(Protocol):
    async def summarize(self, payload: DailySummaryData) -> str:
        """Return an LLM generated summary for the provided payload."""


class GeminiDailySummaryGenerator:
    """LLM backed generator that uses Google Gemini models."""

    def __init__(self, *, api_key: Optional[str], model: str = "gemini-2.5-flash") -> None:
        self._api_key = api_key
        self._model = model
        self._configured = False

    def _ensure_configured(self) -> None:
        if self._configured or not self._api_key:
            return
        genai.configure(api_key=self._api_key)
        self._configured = True

    async def summarize(self, payload: DailySummaryData) -> str:  # type: ignore[override]
        self._ensure_configured()
        if not self._api_key:
            logger.debug("Gemini API key missing - falling back to heuristic summary")
            return self._fallback_summary(payload)

        prompt = self._build_prompt(payload)
        model = genai.GenerativeModel(self._model)
        try:
            response = await asyncio.to_thread(model.generate_content, prompt)
            text = getattr(response, "text", None)
            if not text:
                logger.warning("Gemini response did not contain text output; falling back")
                return self._fallback_summary(payload)
            return text.strip()
        except (GoogleAPIError, ValueError) as exc:
            logger.exception("Gemini summarisation failed: %s", exc)
            return self._fallback_summary(payload)
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Unexpected Gemini error: %s", exc)
            return self._fallback_summary(payload)

    @staticmethod
    def _build_prompt(payload: DailySummaryData) -> str:
        metric_lines = []
        for metric in payload.metrics:
            base = f"- {metric.label}: {metric.value}"
            if metric.unit:
                base += f" {metric.unit}"
            if metric.change_percentage is not None:
                base += f" ({metric.change_percentage:+.1f}% vs previous)"
            if metric.notes:
                base += f" — {metric.notes}"
            metric_lines.append(base)

        metrics_block = "\n".join(metric_lines)
        return (
            "You are a business insights assistant. Given the metrics below, "
            "write a concise daily summary with three bullet points and one "
            "recommended action. Keep the tone optimistic but realistic.\n\n"
            f"Business: {payload.business.name} (ID {payload.business.business_id})\n"
            f"Location: {payload.business.location or 'Not specified'}\n"
            f"Report Date: {payload.date}\n"
            f"Metrics:\n{metrics_block}\n\n"
            "Output format:\n"
            "Summary:\n- bullet\n- bullet\n- bullet\nAction: sentence highlighting one actionable recommendation."
        )

    @staticmethod
    def _fallback_summary(payload: DailySummaryData) -> str:
        highlights = []
        for metric in payload.metrics[:3]:
            unit = f" {metric.unit}" if metric.unit else ""
            highlights.append(f"{metric.label}: {metric.value}{unit}")
        bullet_section = "\n".join(f"- {line}" for line in highlights)
        return (
            f"Summary for {payload.business.name} on {payload.date}:\n"
            f"{bullet_section}\n"
            "Action: Review detailed metrics for deeper insights."
        )


class DailySummaryService:
    """Service that orchestrates metric retrieval and LLM analysis."""

    def __init__(
        self,
        client: JavaServiceClient,
        *,
        summarizer: Optional[DailySummaryGenerator] = None,
        analytics_repository: Optional[AnalyticsRepository] = None,
        master_data: Optional[MasterDataRepository] = None,
    ) -> None:
        self._client = client
        self._summarizer = summarizer or GeminiDailySummaryGenerator(api_key=None)
        self._analytics = analytics_repository
        self._master_data = master_data
        if self._client.use_mock_data:
            store = get_mock_store()
            self._analytics = analytics_repository or store.analytics
            self._master_data = master_data or store.master_data

    async def generate(self, request: DailySummaryRequest) -> DailySummaryResponse:
        logger.info(
            "Generating daily summary for business %s", request.business_id
        )
        payload = (
            await self._collect_mock_data(request)
            if self._client.use_mock_data
            else await self._fetch_live_data(request)
        )

        summary = await self._summarizer.summarize(payload)
        return DailySummaryResponse(**payload.model_dump(), summary=summary)

    async def _fetch_live_data(self, request: DailySummaryRequest) -> DailySummaryData:
        try:
            raw = await self._client.post(
                "/business/daily-summary", request.model_dump(exclude_none=True)
            )
            return DailySummaryData(**raw)
        except ServiceError:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Failed to fetch daily metrics from Java backend")
            raise ServiceError("Failed to fetch daily metrics", cause=exc)

    async def _collect_mock_data(self, request: DailySummaryRequest) -> DailySummaryData:
        if not self._analytics or not self._master_data:
            raise RuntimeError("Mock repositories for daily summary are not configured")

        business_record = self._master_data.get_business(request.business_id)
        if not business_record:
            raise ServiceError(f"Business '{request.business_id}' not found")

        analytics_request = AnalyticsRequest(
            business_id=request.business_id,
            metrics=request.metrics or list(_DEFAULT_METRICS),
            period=request.period,
        )
        report = await self._analytics.generate_report(analytics_request)
        metrics = self._build_metrics(report)
        business_summary = BusinessSummary(
            business_id=business_record.business_id,
            name=business_record.name,
            location=business_record.location,
            tags=list(business_record.tags),
        )
        return DailySummaryData(
            business=business_summary,
            date=self._resolve_date(request.date),
            generated_at=self._utc_now_iso(),
            metrics=metrics,
        )

    @staticmethod
    def _resolve_date(raw: Optional[str]) -> str:
        if raw:
            return raw
        return datetime.now(timezone.utc).date().isoformat()

    @staticmethod
    def _utc_now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _build_metrics(self, report: AnalyticsResponse) -> List[DailySummaryMetric]:
        metrics: List[DailySummaryMetric] = []
        metrics.append(
            DailySummaryMetric(
                key="footfall",
                label="Appointments today",
                value=report.footfall,
                unit="visits",
            )
        )

        currency, revenue_value = self._parse_currency(report.revenue)
        if revenue_value is not None:
            metrics.append(
                DailySummaryMetric(
                    key="total_revenue",
                    label="Total revenue",
                    value=revenue_value,
                    unit=currency,
                )
            )

        invoice_summary = report.invoice_summary
        if invoice_summary is not None:
            metrics.append(
                DailySummaryMetric(
                    key="invoice_count",
                    label="Invoices issued",
                    value=invoice_summary.total,
                )
            )
            metrics.append(
                DailySummaryMetric(
                    key="paid_revenue",
                    label="Paid revenue",
                    value=invoice_summary.paid_total,
                    unit=invoice_summary.currency,
                )
            )
            metrics.append(
                DailySummaryMetric(
                    key="outstanding_revenue",
                    label="Outstanding revenue",
                    value=invoice_summary.outstanding_total,
                    unit=invoice_summary.currency,
                )
            )

        appointment_summary = report.appointment_summary
        if appointment_summary is not None:
            metrics.append(
                DailySummaryMetric(
                    key="unique_customers",
                    label="Unique customers served",
                    value=appointment_summary.unique_customers,
                )
            )

        lead_summary = report.lead_summary
        if lead_summary is not None:
            metrics.append(
                DailySummaryMetric(
                    key="leads_created",
                    label="New leads",
                    value=lead_summary.total,
                )
            )

        if report.top_appointment_service is not None:
            metrics.append(
                DailySummaryMetric(
                    key="top_service",
                    label="Most booked service",
                    value=report.top_appointment_service.name,
                    notes=f"{report.top_appointment_service.booking_count} bookings",
                )
            )

        if report.highest_revenue_service is not None:
            metrics.append(
                DailySummaryMetric(
                    key="highest_revenue_service",
                    label="Top revenue service",
                    value=report.highest_revenue_service.name,
                    unit=report.highest_revenue_service.currency,
                    notes=f"{report.highest_revenue_service.total_revenue:.2f} total",
                )
            )

        return metrics

    @staticmethod
    def _parse_currency(value: str) -> tuple[Optional[str], Optional[float]]:
        if not value:
            return None, None
        raw = value.strip()
        if not raw:
            return None, None
        parts = raw.split(" ", 1)
        currency: Optional[str]
        numeric_part: str
        if len(parts) == 2:
            currency, numeric_part = parts
        else:
            currency = None
            numeric_part = parts[0]
        normalized = numeric_part.replace(",", "")
        try:
            number = float(normalized)
            return currency, number
        except ValueError:
            logger.debug("Unable to parse revenue value '%s'", value)
            return currency, None
