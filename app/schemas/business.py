from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class BusinessSummary(BaseModel):
    """Lightweight projection of a business in the directory."""

    business_id: str
    name: str
    location: Optional[str] = None
    tags: List[str] = []


class BusinessSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Text fragment to search for")
    limit: int = Field(10, ge=1, le=25, description="Maximum number of businesses to return")


class BusinessSearchResponse(BaseModel):
    query: str
    total: int
    items: List[BusinessSummary]


class ServiceSummary(BaseModel):
    service_id: int
    name: str
    category: Optional[str] = None
    duration_minutes: Optional[int] = None
    price: Optional[float] = None


class ServiceLookupRequest(BaseModel):
    service_name: str = Field(..., min_length=1, description="Service name or keyword")
    business_id: Optional[str] = Field(None, description="Exact business identifier")
    business_name: Optional[str] = Field(None, description="Business name fragment when id is unknown")
    limit: int = Field(5, ge=1, le=20, description="Maximum number of services to return")

    @model_validator(mode="after")
    def validate_business_selector(cls, values: "ServiceLookupRequest") -> "ServiceLookupRequest":
        if not values.business_id and not values.business_name:
            raise ValueError("Either business_id or business_name must be provided")
        return values


class ServiceLookupResponse(BaseModel):
    query: str
    business: BusinessSummary
    matches: List[ServiceSummary]
    exact_match: Optional[ServiceSummary] = None
    message: Optional[str] = None
