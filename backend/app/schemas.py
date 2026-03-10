from pydantic import BaseModel, EmailStr
from typing import Any

class CrawlerRunRequest(BaseModel):
    site: str = "all"

class CrawlerRunResponse(BaseModel):
    success: bool
    message: str
    collected_count: int
    data: list[dict[str, Any]] | None = None
    saved_file: str | None = None
    site_counts: dict[str, int] | None = None
    errors: dict[str, str] | None = None


class SummaryEmailRequest(BaseModel):
    date: str
    email: EmailStr
    llm_model: str = "openai"


class SummaryEmailResponse(BaseModel):
    success: bool
    message: str
    summary_preview: str | None = None


class RiskEventRequest(BaseModel):
    date: str
    llm_model: str = "gemini-flash"


class RiskEventItem(BaseModel):
    event_id: str
    event_name: str
    severity: str
    summary: str
    impact_modes: list[str]
    impact_regions: list[str]
    impact_keywords: list[str]
    relevant_sites: list[str]
    selection_hint: str
    why_it_matters: str


class RiskEventResponse(BaseModel):
    success: bool
    message: str
    events: list[RiskEventItem]


class RiskReportRequest(BaseModel):
    date: str
    llm_model: str = "gemini-flash"
    selected_event_id: str | None = None
    selected_event_name: str | None = None
    selected_sites: list[str] = []


class RiskReportResponse(BaseModel):
    success: bool
    message: str
    report_text: str
    html: str | None = None

class ExportGenerateRequest(BaseModel):
    date: str | None = None
    llm_model: str = "gemini-flash"

class ExportJsonResponse(BaseModel):
    success: bool
    filename: str
    count: int
    saved_path: str | None = None

class ExportGcsResponse(BaseModel):
    success: bool
    date: str
    bucket_name: str
    crawled_news: dict[str, Any]
    risk_events: dict[str, Any]