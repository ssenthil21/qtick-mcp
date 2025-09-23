from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class BusinessSummary(BaseModel):
    """Lightweight projection of a business in the directory."""

    business_id: int
    name: str
    location: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


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
    business_id: Optional[int] = Field(None, description="Exact business identifier")
    business_name: Optional[str] = Field(None, description="Business name fragment when id is unknown")
    limit: int = Field(5, ge=1, le=20, description="Maximum number of services to return")

    @model_validator(mode="after")
    def validate_business_selector(cls, values: "ServiceLookupRequest") -> "ServiceLookupRequest":
        if not values.business_id and values.business_name:
            normalized = values.business_name.strip()
            if not normalized:
                raise ValueError("business_name cannot be empty when provided")
            values.business_name = normalized
        return values


class BusinessServiceMatch(BaseModel):
    business: BusinessSummary
    services: List[ServiceSummary]


class ServiceLookupResponse(BaseModel):
    query: str
    business: Optional[BusinessSummary] = None
    matches: List[ServiceSummary] = Field(default_factory=list)
    exact_match: Optional[ServiceSummary] = None
    message: Optional[str] = None
    business_candidates: Optional[List[BusinessSummary]] = None
    service_matches: Optional[List[BusinessServiceMatch]] = None
