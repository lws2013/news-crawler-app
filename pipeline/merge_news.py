"""
크롤링 + 웹검색 결과를 병합하고 URL 기준으로 중복 제거
"""

import json
from pathlib import Path
from urllib.parse import urlparse

OUTPUT_DIR = Path("pipeline/output")


def normalize_url(url: str) -> str:
    """URL 정규화 (쿼리 파라미터 제거, 소문자 변환)"""
    parsed = urlparse(url.strip().lower())
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")


def deduplicate(articles: list[dict]) -> list[dict]:
    """URL 기준 중복 제거 (먼저 나온 것 우선)"""
    seen_urls = set()
    unique = []

    for article in articles:
        url = article.get("url", "")
        if not url:
            continue

        norm_url = normalize_url(url)
        if norm_url not in seen_urls:
            seen_urls.add(norm_url)
            unique.append(article)

    return unique


def main():
    # 크롤링 결과 로드
    crawled_path = OUTPUT_DIR / "raw_crawled.json"
    crawled = []
    if crawled_path.exists():
        with open(crawled_path, "r", encoding="utf-8") as f:
            crawled = json.load(f)
        print(f"📥 크롤링 데이터: {len(crawled)}건")

    # 검색 결과 로드
    search_path = OUTPUT_DIR / "raw_search.json"
    searched = []
    if search_path.exists():
        with open(search_path, "r", encoding="utf-8") as f:
            searched = json.load(f)
        print(f"📥 검색 데이터: {len(searched)}건")

    # 병합 + 중복제거
    merged = crawled + searched
    unique = deduplicate(merged)

    print(f"🔀 병합: {len(merged)}건 → 중복제거 후: {len(unique)}건")

    # 저장
    output_path = OUTPUT_DIR / "all_news.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(unique, f, ensure_ascii=False, indent=2)

    print(f"📦 최종 데이터 → {output_path}")


if __name__ == "__main__":
    main()
