from typing import Any
from pathlib import Path
import sys
import json
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parents[3]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from news_crawler.crawler_demo_busanpa import crawl_busanpa
from news_crawler.crawler_demo_cargonews import crawl_cargonews
from news_crawler.crawler_demo_cello import crawl_cello
from news_crawler.crawler_demo_flexport import crawl_flexport
from news_crawler.crawler_demo_iata import crawl_iata
from news_crawler.crawler_demo_kita import crawl_kita
from news_crawler.crawler_demo_kotra import crawl_kotra
from news_crawler.crawler_demo_ksg import crawl_ksg
from news_crawler.crawler_demo_oceanpress import crawl_oceanpress
from news_crawler.crawler_demo_sea import crawl_sea
from news_crawler.crawler_demo_shippingnews import crawl_shippingnews
from news_crawler.crawler_demo_surff import crawl_surff
from news_crawler.crawler_demo_ulogistics import crawl_ulogistics


def save_crawled_data(site: str, data: list[dict[str, Any]]) -> str:
    data_dir = PROJECT_ROOT / "backend" / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = data_dir / f"{site}_{timestamp}.json"

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return str(file_path)


def run_news_crawler(site: str) -> dict[str, Any]:
    site = site.lower().strip()

    site_map = {
        "busanpa": crawl_busanpa,
        "cargonews": crawl_cargonews,
        "cello": crawl_cello,
        "flexport": crawl_flexport,
        "iata": crawl_iata,
        "kita": crawl_kita,
        "kotra": crawl_kotra,
        "ksg": crawl_ksg,
        "oceanpress": crawl_oceanpress,
        "sea": crawl_sea,
        "shippingnews": crawl_shippingnews,
        "surff": crawl_surff,
        "ulogistics": crawl_ulogistics,
    }

    if site == "all":
        all_results = []
        site_counts: dict[str, int] = {}

        for site_name, crawler_func in site_map.items():
            try:
                print(f"[INFO] Start crawler: {site_name}")
                crawled = crawler_func()

                for item in crawled:
                    item["source"] = site_name

                all_results.extend(crawled)
                site_counts[site_name] = len(crawled)
                print(f"[INFO] Completed crawler: {site_name} ({len(crawled)}건)")
            except Exception as e:
                site_counts[site_name] = 0
                print(f"[ERROR] crawler failed for {site_name}: {e}")

        saved_file = save_crawled_data("all", all_results)

        return {
            "message": "Crawler completed for all sites",
            "collected_count": len(all_results),
            "data": all_results,
            "saved_file": saved_file,
            "site_counts": site_counts,
        }

    if site not in site_map:
        raise ValueError(f"Unsupported site: {site}")

    crawled_data = site_map[site]()
    for item in crawled_data:
        item["source"] = site

    saved_file = save_crawled_data(site, crawled_data)
    site_counts = {site: len(crawled_data)}

    return {
        "message": f"Crawler completed for site={site}",
        "collected_count": len(crawled_data),
        "data": crawled_data,
        "saved_file": saved_file,
        "site_counts": site_counts,
    }