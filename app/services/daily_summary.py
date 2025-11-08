from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Protocol

from google.api_core.exceptions import GoogleAPIError
import google.generativeai as genai
import json
import sys
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
        sys.stdout.reconfigure(encoding='utf-8')
        prompt = self._build_prompt(payload)
        model = genai.GenerativeModel(self._model)
        try:
            response = await asyncio.to_thread(model.generate_content, prompt)
            text = getattr(response, "text", None)
            if not text:
                logger.warning("Gemini response did not contain text output; falling back")
                return self._fallback_summary(payload)
            safe_text = text.strip().encode('utf-8', 'replace').decode()
            print(safe_text)
            return safe_text.strip()
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
            if isinstance(metric, DailySummaryMetric):
                details = {
                    key: value
                    for key, value in metric.model_dump().items()
                    if value not in (None, "")
                }
                label = details.pop("label", metric.key)
                value = details.pop("value", "")
                unit = details.pop("unit", None)
                description = f"{label}: {value}"
                if unit:
                    description = f"{description} {unit}"
                if details:
                    extras = ", ".join(f"{k}={v}" for k, v in details.items())
                    description = f"{description} ({extras})"
                metric_lines.append(f"- {description}")
            else:
                metric_lines.append(f"- {metric}")

        metrics_block = "\n".join(metric_lines)
        
        prompt = f"""
        You are a business analytics assistant.
        Generate a concise, professional **Markdown** daily summary for the given JSON data.

        ### Time & Date Rules
        - All timestamps in the data are in **UTC**.
        - Convert all times to **India Standard Time (UTC +5:30)** before deciding the summary date.
        - Use the IST date as the reporting date in the title.

        ### Data Interpretation Rules
        - Merge all metric sources (billing, daily stats, performance).
        - If some sections show 0 but others have valid numbers (like totalSales > 0), use valid data.
        - Prefer `totalSales` and `billCount` as primary metrics.
        - Format all currency values as ₹ with two decimals.

        ### Markdown Output Format
        ##  Business Daily Summary – [IST date]
        **Business ID:** [id]  
        **Name:** [name]  
        **Location:** [location]

        ###  Sales Overview
        | Metric | Value |
        |---------|------:|
        | Total Bills | n |
        | Total Sales | ₹xx.xx |
        | Gross Amount | ₹xx.xx |
        | Tax Amount | ₹xx.xx |
        | Discount | ₹xx.xx |
        | Collected | ₹xx.xx |

        **Payment Breakdown:** Cash ₹xx.xx • QR ₹xx.xx • Card ₹xx.xx

        ###  Sales Performance
        | Period | Sales |
        |:--------|------:|
        | Last Day | ₹xx.xx |
        | Last 7 Days | ₹xx.xx |
        | Last 30 Days | ₹xx.xx |

        ###  Summary Insight
        2–3 lines summarizing performance, trends, and anomalies.

        ### Data:
        {metrics_block}

        Now generate the Markdown summary in IST.
        """

        return prompt
        prompt = f"""
        You are a business data analysis assistant that writes clear and professional daily summaries for small businesses.

        ### Instructions
        Given the JSON data below, create a **structured business daily summary** using this format:
        - Title: "🧾 Business Daily Summary – [date]"
        - Show key business info (ID, Name, Location)
        - Include sections with emojis:
         Sales Overview (with totals and payment type breakdown)
         Sales Performance (comparisons if available)
         Customer & Service Activity
         Stylist & Service Stats
         Ratings
         Summary Insight (brief 2–3 line interpretation)

        Rules:
        - Use markdown tables where suitable
        - Format currency as ₹ with two decimals
        - If values are missing or zero, write "No data recorded"
        - Keep the tone analytical but friendly
        - Do not repeat identical values
        - End with one-sentence insight

        Now generate the summary for this JSON data:
        {metrics_block}
        """
        return prompt 
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
            if isinstance(metric, DailySummaryMetric):
                unit = f" {metric.unit}" if metric.unit else ""
                highlights.append(f"{metric.label}: {metric.value}{unit}")
            else:
                highlights.append(str(metric))
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
            startDate = datetime.strptime(request.date, "%Y-%m-%d").strftime("%d %b %Y")
            params = {
               "startTime": startDate,
                "endTime": startDate
            }
            sales = await self._client.get(
                f"reports/sales-report/{request.business_id}", params=params
            )
            
            d = datetime.strptime(request.date, "%Y-%m-%d")
            new_date = d + timedelta(days=5)
            formatted = new_date.strftime("%Y/%m/%d")
            params = {
               "date": formatted
            }
            dailySales = await self._client.get(
                f"reports/daily-sales-report/{request.business_id}", params=params
            )
            metrics = []
            if sales:
                metrics.append(json.dumps(sales, indent=2))
            if dailySales:
                metrics.append(json.dumps(dailySales, indent=2))

            print(metrics)
            # Build structured summary
            summary = DailySummaryData(
                business=BusinessSummary(
                    business_id=request.business_id,
                    name=getattr(request, "business_name", "Unknown")
                ),
                date=request.date,
                generated_at=datetime.now(timezone.utc).isoformat(),
                metrics=metrics
            )

            return summary
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
