from pathlib import Path
from datetime import datetime
from typing import Any
import json
import os

from app.services.summary_service import load_latest_crawled_articles, generate_risk_events

try:
    from google.cloud import storage
except Exception:
    storage = None

PROJECT_ROOT = Path(__file__).resolve().parents[2]

def get_export_date_str(target_date: str | None = None) -> str:
    if target_date:
        return target_date.replace("-", "")
    return datetime.now().strftime("%Y%m%d")

def get_export_dir(target_date: str | None = None) -> Path:
    date_folder = target_date or datetime.now().strftime("%Y-%m-%d")
    export_dir = PROJECT_ROOT / "data" / "export" / date_folder
    export_dir.mkdir(parents=True, exist_ok=True)
    return export_dir

def save_json_file(data: Any, filename: str, target_date: str | None = None) -> str:
    export_dir = get_export_dir(target_date)
    file_path = export_dir / filename

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return str(file_path)

def build_crawled_news_export(target_date: str | None = None) -> dict[str, Any]:
    date_str = get_export_date_str(target_date)
    articles = load_latest_crawled_articles()

    filename = f"crawled_news_{date_str}.json"
    saved_path = save_json_file(articles, filename, target_date)

    return {
        "filename": filename,
        "saved_path": saved_path,
        "data": articles,
        "count": len(articles),
    }

def build_risk_events_export(
    target_date: str | None = None,
    llm_model: str = "gemini-flash",
) -> dict[str, Any]:
    date_str = get_export_date_str(target_date)
    articles = load_latest_crawled_articles()

    events = generate_risk_events(
        target_date=target_date or datetime.now().strftime("%Y-%m-%d"),
        articles=articles,
        llm_model=llm_model,
    )

    filename = f"risk_events_{date_str}.json"
    saved_path = save_json_file(events, filename, target_date)

    return {
        "filename": filename,
        "saved_path": saved_path,
        "data": events,
        "count": len(events),
    }

def upload_json_to_gcs(
    bucket_name: str,
    blob_path: str,
    data: Any,
) -> str:
    if storage is None:
        raise RuntimeError("google-cloud-storage 패키지가 설치되지 않았습니다.")

    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_path)
    blob.upload_from_string(
        json.dumps(data, ensure_ascii=False, indent=2),
        content_type="application/json; charset=utf-8",
    )
    return f"gs://{bucket_name}/{blob_path}"

def export_and_upload_to_gcs(
    target_date: str | None = None,
    llm_model: str = "gemini-flash",
) -> dict[str, Any]:
    bucket_name = os.getenv("GCS_BUCKET_NAME", "").strip()
    if not bucket_name:
        raise ValueError("GCS_BUCKET_NAME 환경변수가 설정되지 않았습니다.")

    date_folder = target_date or datetime.now().strftime("%Y-%m-%d")
    date_str = get_export_date_str(target_date)

    crawled_result = build_crawled_news_export(target_date)
    events_result = build_risk_events_export(target_date, llm_model)

    crawled_blob = f"external_output/{date_folder}/crawled_news_{date_str}.json"
    events_blob = f"external_output/{date_folder}/risk_events_{date_str}.json"

    crawled_gcs_path = upload_json_to_gcs(bucket_name, crawled_blob, crawled_result["data"])
    events_gcs_path = upload_json_to_gcs(bucket_name, events_blob, events_result["data"])

    return {
        "date": date_folder,
        "bucket_name": bucket_name,
        "crawled_news": {
            "filename": crawled_result["filename"],
            "count": crawled_result["count"],
            "gcs_path": crawled_gcs_path,
        },
        "risk_events": {
            "filename": events_result["filename"],
            "count": events_result["count"],
            "gcs_path": events_gcs_path,
        },
    }