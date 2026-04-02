"""
기존 14개 크롤러를 순차 실행하여 raw_crawled.json으로 수집
─────────────────────────────────────────────────
실제 크롤러 구조 확인 결과:
- 함수명 패턴: crawl_사이트명() (예: crawl_busanpa)
- Playwright 기반 headless 브라우저 사용
- 반환 형식: [{"url", "category", "title", "date", "content", "images"}, ...]
"""

import json
import importlib
import traceback
from datetime import datetime
from pathlib import Path

# ── 크롤러 모듈 매핑 ──
# key: 소스명
# value: (모듈 경로, 함수명)
# ⚠️ 함수명이 다른 크롤러가 있으면 여기서 수정하세요
CRAWLER_MAP = {
    "busanpa":       ("backend.news_crawler.crawler_demo_busanpa",      "crawl_busanpa"),
    "cargonews":     ("backend.news_crawler.crawler_demo_cargonews",    "crawl_cargonews"),
    "cello":         ("backend.news_crawler.crawler_demo_cello",        "crawl_cello"),
    "flexport":      ("backend.news_crawler.crawler_demo_flexport",     "crawl_flexport"),
    "iata":          ("backend.news_crawler.crawler_demo_iata",         "crawl_iata"),
    "kita":          ("backend.news_crawler.crawler_demo_kita",         "crawl_kita"),
    "kotra":         ("backend.news_crawler.crawler_demo_kotra",        "crawl_kotra"),
    "ksg":           ("backend.news_crawler.crawler_demo_ksg",          "crawl_ksg"),
    "oceanpress":    ("backend.news_crawler.crawler_demo_oceanpres",    "crawl_oceanpres"),
    "sea":           ("backend.news_crawler.crawler_demo_sea",          "crawl_sea"),
    "shippingnews":  ("backend.news_crawler.crawler_demo_shippingne",   "crawl_shippingne"),
    "surff":         ("backend.news_crawler.crawler_demo_surff",        "crawl_surff"),
    "ulogistics":    ("backend.news_crawler.crawler_demo_ulogistics",   "crawl_ulogistics"),
}

OUTPUT_DIR = Path("pipeline/output")


def find_crawl_function(module, expected_func_name: str):
    """
    크롤러 함수를 찾는다.
    1순위: 예상 함수명 (crawl_사이트명)
    2순위: 'crawl_'로 시작하는 함수
    3순위: crawl, get_news, main, run
    """
    # 1순위: 예상 함수명
    if hasattr(module, expected_func_name):
        return getattr(module, expected_func_name)

    # 2순위: crawl_ 로 시작하는 함수 탐색
    for attr_name in dir(module):
        if attr_name.startswith("crawl_") and callable(getattr(module, attr_name)):
            return getattr(module, attr_name)

    # 3순위: 일반적인 함수명
    for func_name in ["crawl", "get_news", "main", "run"]:
        if hasattr(module, func_name):
            func = getattr(module, func_name)
            if callable(func):
                return func

    return None


def run_all_crawlers() -> list[dict]:
    """모든 크롤러를 실행하고 결과를 하나의 리스트로 합침"""
    all_articles = []
    success_count = 0
    fail_count = 0

    for source_name, (module_path, func_name) in CRAWLER_MAP.items():
        print(f"\n{'='*50}")
        print(f"🔍 크롤링 중: {source_name}")
        print(f"   모듈: {module_path}")
        print(f"   함수: {func_name}")

        try:
            module = importlib.import_module(module_path)
            crawl_func = find_crawl_function(module, func_name)

            if crawl_func is None:
                print(f"  ⚠️ {source_name}: 크롤링 함수를 찾을 수 없습니다. 스킵.")
                fail_count += 1
                continue

            print(f"  → {crawl_func.__name__}() 실행 중...")
            articles = crawl_func()

            if articles is None:
                articles = []

            # 각 기사에 메타데이터 추가
            for article in articles:
                article["source"] = source_name
                article["crawled_at"] = datetime.now().isoformat()

                # content가 있으면 snippet 생성 (LLM 요약용, 300자 제한)
                if article.get("content") and not article.get("snippet"):
                    article["snippet"] = article["content"][:300].strip()

            all_articles.extend(articles)
            success_count += 1
            print(f"  ✅ {source_name}: {len(articles)}건 수집")

        except Exception as e:
            fail_count += 1
            print(f"  ❌ {source_name} 크롤링 실패: {e}")
            traceback.print_exc()
            continue

    print(f"\n{'='*50}")
    print(f"📊 크롤링 결과: 성공 {success_count}개 / 실패 {fail_count}개")
    return all_articles


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    articles = run_all_crawlers()

    output_path = OUTPUT_DIR / "raw_crawled.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)

    print(f"\n📦 총 {len(articles)}건 크롤링 완료 → {output_path}")


if __name__ == "__main__":
    main()
