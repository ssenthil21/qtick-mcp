from __future__ import annotations

from functools import lru_cache

from fastapi import Depends

from app.clients.java import JavaServiceClient
from app.config import Settings, get_settings
from app.services import (
    AnalyticsService,
    AppointmentService,
    BusinessDirectoryService,
    CampaignService,
    DailySummaryService,
    InvoiceService,
    LeadService,
    LiveOperationsService,
)
from app.services.daily_summary import GeminiDailySummaryGenerator


@lru_cache(maxsize=1)
def get_java_client_cached() -> JavaServiceClient:
    settings = get_settings()
    print(str(settings))
    return JavaServiceClient(
        settings.java_service_base_url,
        timeout=settings.java_service_timeout,
        use_mock_data=settings.use_mock_data,
        token=settings.java_service_token,
    )


def get_java_client(settings: Settings = Depends(get_settings)) -> JavaServiceClient:
    return get_java_client_cached()


def get_appointment_service(
    client: JavaServiceClient = Depends(get_java_client),
) -> AppointmentService:
    return AppointmentService(client)


def get_invoice_service(
    client: JavaServiceClient = Depends(get_java_client),
) -> InvoiceService:
    return InvoiceService(client)


def get_lead_service(
    client: JavaServiceClient = Depends(get_java_client),
) -> LeadService:
    return LeadService(client)


def get_campaign_service(
    client: JavaServiceClient = Depends(get_java_client),
) -> CampaignService:
    return CampaignService(client)


def get_analytics_service(
    client: JavaServiceClient = Depends(get_java_client),
) -> AnalyticsService:
    return AnalyticsService(client)


def get_business_directory_service(
    client: JavaServiceClient = Depends(get_java_client),
) -> BusinessDirectoryService:
    return BusinessDirectoryService(client)


def get_live_ops_service(
    client: JavaServiceClient = Depends(get_java_client),
) -> LiveOperationsService:
    return LiveOperationsService(client)


def get_daily_summary_service(
    client: JavaServiceClient = Depends(get_java_client),
    settings: Settings = Depends(get_settings),
) -> DailySummaryService:
    summarizer = GeminiDailySummaryGenerator(
        api_key=settings.google_api_key,
        model=settings.agent_google_model,
    )
    return DailySummaryService(client, summarizer=summarizer)
