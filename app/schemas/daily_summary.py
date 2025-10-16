from __future__ import annotations

from datetime import date
from typing import List, Optional, Union

from pydantic import BaseModel, Field, field_validator

from app.schemas.business import BusinessSummary


class DailySummaryMetric(BaseModel):
    """Structured metric included in the daily business summary."""

    key: str = Field(..., description="Machine readable metric identifier")
    label: str = Field(..., description="Human friendly label for the metric")
    value: Union[int, float, str] = Field(
        ..., description="Primary metric value, can be numeric or descriptive"
    )
    unit: Optional[str] = Field(
        default=None, description="Optional unit for the metric value"
    )
    change_percentage: Optional[float] = Field(
        default=None,
        description=(
            "Percentage change compared to the previous comparable period."
        ),
    )
    notes: Optional[str] = Field(
        default=None,
        description="Free-form context that further explains the metric",
    )


class DailySummaryRequest(BaseModel):
    """Request payload for generating a daily business summary."""

    business_id: int = Field(..., description="Identifier of the business")
    date: Optional[str] = Field(
        default=None,
        description="ISO formatted date (YYYY-MM-DD). Defaults to today when omitted.",
    )
    metrics: Optional[List[str]] = Field(
        default=None,
        description="Optional list of metric identifiers requested by the client.",
    )
    period: str = Field(
        default="day",
        description="Reporting period hint forwarded to the analytics backend.",
    )

    @field_validator("date")
    @classmethod
    def _validate_date(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        try:
            date.fromisoformat(value)
        except ValueError as exc:  # pragma: no cover - schema level validation
            raise ValueError("date must be provided in ISO format YYYY-MM-DD") from exc
        return value


class DailySummaryData(BaseModel):
    """Structured metrics ready for LLM analysis."""

    business: BusinessSummary
    date: str
    generated_at: str
    metrics: List[DailySummaryMetric]


class DailySummaryResponse(DailySummaryData):
    """Response returned to clients including LLM generated insights."""

    summary: str = Field(..., description="Narrative daily summary produced by the LLM")
