
from fastapi import APIRouter
from app.schemas.analytics import AnalyticsRequest, AnalyticsResponse

router = APIRouter()

@router.post("/report", response_model=AnalyticsResponse)
def get_analytics(req: AnalyticsRequest):
    # mock
    return AnalyticsResponse(
        footfall=42,
        revenue="SGD 1,540",
        report_generated_at="2025-09-05T15:03:10+08:00"
    )
