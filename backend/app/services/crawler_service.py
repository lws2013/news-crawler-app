from pathlib import Path
from datetime import datetime
import json
import sys
from typing import Callable, Any

# backend/app/services/crawler_service.py 기준
# parents[0] = services
# parents[1] = app
# parents[2] = backend
PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from news_crawler.crawler_demo_busanpa import crawl_busanpa
from news_crawler.crawler_demo_iata import crawl_iata

# 나머지 사이트 크롤러가 있으면 같은 방식으로 추가
from news_crawler.crawler_demo_cargonews import crawl_cargonews
from news_crawler.crawler_demo_cello import crawl_cello
from news_crawler.crawler_demo_flexport import crawl_flexport
from news_crawler.crawler_demo_kita import crawl_kita
from news_crawler.crawler_demo_kotra import crawl_kotra
from news_crawler.crawler_demo_ksg import crawl_ksg
from news_crawler.crawler_demo_oceanpress import crawl_oceanpress
from news_crawler.crawler_demo_sea import crawl_sea
from news_crawler.crawler_demo_shippingnews import crawl_shippingnews
from news_crawler.crawler_demo_surff import crawl_surff
from news_crawler.crawler_demo_ulogistics import crawl_ulogistics

def get_site_map() -> dict[str, Callable[[], list[dict[str, Any]]]]:
    site_map: dict[str, Callable[[], list[dict[str, Any]]]] = {
        "busanpa": crawl_busanpa,
        "iata": crawl_iata,
    }

    # 실제 구현된 사이트만 주석 해제해서 추가
    site_map["cargonews"] = crawl_cargonews
    site_map["cello"] = crawl_cello
    site_map["flexport"] = crawl_flexport
    site_map["kita"] = crawl_kita
    site_map["kotra"] = crawl_kotra
    site_map["ksg"] = crawl_ksg
    site_map["oceanpress"] = crawl_oceanpress
    site_map["sea"] = crawl_sea
    site_map["shippingnews"] = crawl_shippingnews
    site_map["surff"] = crawl_surff
    site_map["ulogistics"] = crawl_ulogistics

    return site_map

def normalize_articles(site_name: str, crawled: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []

    for item in crawled or []:
        normalized.append(
            {
                "source": site_name,
                "url": item.get("url", ""),
                "category": item.get("category", ""),
                "title": item.get("title", ""),
                "date": item.get("date", ""),
                "content": item.get("content", ""),
                "images": item.get("images", []) or [],
            }
        )

    return normalized

def save_crawled_data(data: list[dict[str, Any]]) -> str:
    data_dir = PROJECT_ROOT / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = data_dir / f"crawled_news_{timestamp}.json"

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return str(file_path)

def run_single_crawler(site_name: str, crawler_func: Callable[[], list[dict[str, Any]]]) -> list[dict[str, Any]]:
    print(f"[INFO] start crawler: {site_name}")
    crawled = crawler_func()
    normalized = normalize_articles(site_name, crawled)
    print(f"[INFO] done crawler: {site_name} / {len(normalized)}건")
    return normalized

def run_news_crawler(site: str = "all") -> dict[str, Any]:
    site_map = get_site_map()

    if site != "all" and site not in site_map:
        raise ValueError(f"지원하지 않는 사이트입니다: {site}")

    all_results: list[dict[str, Any]] = []
    site_counts: dict[str, int] = {}
    errors: dict[str, str] = {}

    if site == "all":
        for site_name, crawler_func in site_map.items():
            try:
                normalized = run_single_crawler(site_name, crawler_func)
                all_results.extend(normalized)
                site_counts[site_name] = len(normalized)
            except Exception as e:
                errors[site_name] = str(e)
                site_counts[site_name] = 0
                print(f"[ERROR] crawler failed for {site_name}: {e}")

        saved_file = save_crawled_data(all_results)

        message = f"Crawler completed for all sites ({len(all_results)}건)"
        if errors:
            failed_sites = ", ".join(errors.keys())
            message += f" / failed: {failed_sites}"

        return {
            "message": message,
            "collected_count": len(all_results),
            "data": all_results,
            "saved_file": saved_file,
            "site_counts": site_counts,
            "errors": errors,
        }

    # 개별 사이트 실행
    try:
        normalized = run_single_crawler(site, site_map[site])
        site_counts[site] = len(normalized)
        saved_file = save_crawled_data(normalized)

        return {
            "message": f"Crawler completed for {site} ({len(normalized)}건)",
            "collected_count": len(normalized),
            "data": normalized,
            "saved_file": saved_file,
            "site_counts": site_counts,
            "errors": {},
        }

    except Exception as e:
        print(f"[ERROR] crawler failed for {site}: {e}")
        raise RuntimeError(f"{site} 크롤러 실행 실패: {e}") from e