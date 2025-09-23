from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class ReviewRecord(BaseModel):
    review_id: str
    business_id: int
    invoice_id: str
    customer_name: str
    status: str
    requested_at: str
    completed_at: Optional[str] = None
    rating: Optional[int] = None
    feedback: Optional[str] = None
