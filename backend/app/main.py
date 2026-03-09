from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import json

from app.schemas import (
    CrawlerRunRequest,
    CrawlerRunResponse,
    SummaryEmailRequest,
    SummaryEmailResponse,
    RiskEventRequest,
    RiskEventResponse,
    RiskEventItem,
    RiskReportRequest,
    RiskReportResponse,
)
from app.services.crawler_service import run_news_crawler
from app.services.summary_service import (
    build_summary_email_payload,
    build_risk_events_payload,
    build_poc_risk_report_payload,
)
from app.services.mail_service import send_html_email

app = FastAPI(title="News Crawler API", version="0.1.0")

origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health_check():
    return {"status": "ok"}


@app.post("/api/crawler/run", response_model=CrawlerRunResponse)
def crawler_run(payload: CrawlerRunRequest):
    result = run_news_crawler(site=payload.site)
    return CrawlerRunResponse(success=True, **result)


@app.get("/api/crawler/json")
def get_crawler_json(file_path: str):
    path = Path(file_path)

    if not path.exists():
        raise HTTPException(status_code=404, detail="JSON file not found")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return {
        "success": True,
        "file_path": str(path),
        "data": data,
    }


@app.post("/api/news/summarize-email", response_model=SummaryEmailResponse)
def summarize_email(payload: SummaryEmailRequest):
    email_payload = build_summary_email_payload(payload.date, payload.llm_model)

    send_html_email(
        to_email=payload.email,
        subject=f"[물류 뉴스 요약] {payload.date}",
        html_body=email_payload["html"],
        text_body=email_payload["summary_text"],
    )

    return SummaryEmailResponse(
        success=True,
        message=f"Summary email sent to {payload.email} using {payload.llm_model}",
        summary_preview=email_payload["summary_text"][:300],
    )


@app.post("/api/risk-events/generate", response_model=RiskEventResponse)
def generate_risk_events_api(payload: RiskEventRequest):
    result = build_risk_events_payload(payload.date, payload.llm_model)
    events = [RiskEventItem(**item) for item in result["events"]]

    return RiskEventResponse(
        success=True,
        message=f"Risk events generated using {payload.llm_model}",
        events=events,
    )


@app.post("/api/risk-report/generate", response_model=RiskReportResponse)
def generate_risk_report(payload: RiskReportRequest):
    result = build_poc_risk_report_payload(
        target_date=payload.date,
        llm_model=payload.llm_model,
        selected_event_name=payload.selected_event_name,
        selected_sites=payload.selected_sites,
    )

    return RiskReportResponse(
        success=True,
        message=f"Risk report generated using {payload.llm_model}",
        report_text=result["report_text"],
        html=result.get("html"),
    )