"""
SCFI & KCCI 운임지수 크롤링 + 이력 관리
─────────────────────────────────────────────────
[SCFI] Shanghai Containerized Freight Index - 매주 금요일 갱신
  소스: https://en.sse.net.cn/indices/scfinew.jsp
  방식: Playwright (JS 동적 로딩)

[KCCI] KOBC Container Composite Index - 매주 월요일 갱신
  소스: https://www.kobc.or.kr/ebz/shippinginfo/kcci/gridList.do
  방식: requests + BeautifulSoup (정적 HTML)

[데이터 저장] data/freight_indices.json (GitHub repo에 커밋)
"""

import json
import re
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

OUTPUT_DIR = Path("pipeline/output")
DATA_DIR = Path("data")
INDICES_FILE = DATA_DIR / "freight_indices.json"


def load_indices() -> dict:
    if INDICES_FILE.exists():
        with open(INDICES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"scfi": [], "kcci": []}


def save_indices(data: dict):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(INDICES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"💾 지수 이력 저장 → {INDICES_FILE}")


def normalize_date(value):
    """허용 포맷:
    - YYYY-MM-DD
    - YYYYMMDD -> YYYY-MM-DD 변환
    그 외는 None
    """
    if value is None:
        return None

    value = str(value).strip()
    if not value:
        return None

    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return value

    if re.fullmatch(r"\d{8}", value):
        return f"{value[:4]}-{value[4:6]}-{value[6:8]}"

    return None


def parse_float(text: str):
    """문자열에서 첫 번째 숫자(float) 추출"""
    if text is None:
        return None

    cleaned = str(text).replace(",", "").strip()
    match = re.search(r"-?\d+(?:\.\d+)?", cleaned)
    if not match:
        return None

    try:
        return float(match.group())
    except ValueError:
        return None


def crawl_kcci() -> dict | None:
    """KCCI 크롤링 (requests + BeautifulSoup)"""
    print("\n🔎 KCCI 크롤링 중...")
    url = "https://www.kobc.or.kr/ebz/shippinginfo/kcci/gridList.do?mId=0304000000"

    try:
        resp = requests.get(
            url,
            timeout=15,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        table = soup.find("table")
        if not table:
            print("  ❌ KCCI 테이블을 찾을 수 없습니다.")
            return None

        headers = [th.get_text(strip=True) for th in table.find_all("th")]
        current_date = None
        previous_date = None
        current_col = None
        previous_col = None

        for i, h in enumerate(headers):
            compact = " ".join(h.split())

            if "Current Index" in compact or "CurrentIndex" in compact:
                match = re.search(r"(\d{4}-\d{2}-\d{2}|\d{8})", compact)
                if match:
                    current_date = normalize_date(match.group(1))
                current_col = i

            elif "Previous Index" in compact or "PreviousIndex" in compact:
                match = re.search(r"(\d{4}-\d{2}-\d{2}|\d{8})", compact)
                if match:
                    previous_date = normalize_date(match.group(1))
                previous_col = i

        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all(["td", "th"])
            cell_texts = [c.get_text(strip=True) for c in cells]

            if "KCCI" in cell_texts:
                current_val = None
                previous_val = None

                if current_col is not None and current_col < len(cell_texts):
                    current_val = parse_float(cell_texts[current_col])

                if previous_col is not None and previous_col < len(cell_texts):
                    previous_val = parse_float(cell_texts[previous_col])

                # fallback: 숫자 2개 추출
                if current_val is None:
                    numeric_vals = []
                    for c in cell_texts:
                        val = parse_float(c)
                        if val is not None and val > 100:
                            numeric_vals.append(val)

                    if len(numeric_vals) >= 1:
                        current_val = numeric_vals[0]
                    if len(numeric_vals) >= 2:
                        previous_val = numeric_vals[1]

                if current_val is not None:
                    result = {
                        "index": "KCCI",
                        "current_value": current_val,
                        "current_date": current_date,
                        "previous_value": previous_val,
                        "previous_date": previous_date,
                        "crawled_at": datetime.now().isoformat(),
                    }
                    print(
                        f"  ✅ KCCI: {current_val} ({current_date}), 이전: {previous_val} ({previous_date})"
                    )
                    return result

        print("  ❌ KCCI 데이터를 찾을 수 없습니다.")
        return None

    except Exception as e:
        print(f"  ❌ KCCI 크롤링 실패: {e}")
        return None


def crawl_scfi() -> dict | None:
    """SCFI 크롤링 (Playwright - 헤더명 기반 컬럼 매핑)"""
    print("\n🔎 SCFI 크롤링 중 (Playwright)...")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  ❌ Playwright가 설치되지 않았습니다.")
        return None

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            page.goto("https://en.sse.net.cn/indices/scfinew.jsp", timeout=30000)
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(3000)

            tables = page.locator("table").all()
            target_table = None

            for table in tables:
                try:
                    text = table.inner_text()
                except Exception:
                    continue

                if (
                    "Comprehensive Index" in text
                    and "Current Index" in text
                    and "Previous Index" in text
                ):
                    target_table = table
                    break

            if target_table is None:
                browser.close()
                print("  ❌ SCFI 대상 테이블을 찾을 수 없습니다.")
                return None

            rows = target_table.locator("tr").all()
            if not rows:
                browser.close()
                print("  ❌ SCFI 테이블 행을 찾을 수 없습니다.")
                return None

            # 1) 헤더 행 찾기
            header_cells = None
            for row in rows:
                cells = row.locator("th, td").all()
                texts = [c.inner_text().strip() for c in cells]
                row_text = " ".join(texts)

                if "Previous Index" in row_text and "Current Index" in row_text:
                    header_cells = texts
                    break

            if not header_cells:
                browser.close()
                print("  ❌ SCFI 헤더 행을 찾을 수 없습니다.")
                return None

            previous_col = None
            current_col = None
            previous_date = None
            current_date = None

            for i, text in enumerate(header_cells):
                compact = " ".join(text.split())

                if "Previous Index" in compact:
                    previous_col = i
                    match = re.search(r"(\d{4}-\d{2}-\d{2}|\d{8})", compact)
                    if match:
                        previous_date = normalize_date(match.group(1))

                elif "Current Index" in compact:
                    current_col = i
                    match = re.search(r"(\d{4}-\d{2}-\d{2}|\d{8})", compact)
                    if match:
                        current_date = normalize_date(match.group(1))

            if previous_col is None or current_col is None:
                browser.close()
                print(
                    f"  ❌ SCFI 컬럼 인덱스 확인 실패. prev={previous_col}, curr={current_col}"
                )
                return None

            # 2) Comprehensive Index 행 찾기
            target_row_cells = None
            for row in rows:
                cells = row.locator("th, td").all()
                texts = [c.inner_text().strip() for c in cells]

                if texts and any("Comprehensive Index" in t for t in texts):
                    target_row_cells = texts
                    break

            if not target_row_cells:
                browser.close()
                print("  ❌ Comprehensive Index 행을 찾을 수 없습니다.")
                return None

            previous_val = None
            current_val = None

            if previous_col < len(target_row_cells):
                previous_val = parse_float(target_row_cells[previous_col])

            if current_col < len(target_row_cells):
                current_val = parse_float(target_row_cells[current_col])

            browser.close()

            if current_val is None:
                print("  ❌ SCFI current value 파싱 실패")
                return None

            result = {
                "index": "SCFI",
                "current_value": current_val,
                "current_date": current_date,
                "previous_value": previous_val,
                "previous_date": previous_date,
                "crawled_at": datetime.now().isoformat(),
            }

            print(
                f"  ✅ SCFI: {current_val} ({current_date}), 이전: {previous_val} ({previous_date})"
            )
            return result

    except Exception as e:
        print(f"  ❌ SCFI 크롤링 실패: {e}")
        return None


def update_history(indices_data: dict, new_data: dict | None, index_name: str):
    """이력 추가 + 기존 잘못된 날짜 자동 정리"""
    if new_data is None:
        return

    key = index_name.lower()
    history = indices_data.get(key, [])
    current_date = normalize_date(new_data.get("current_date"))

    if not current_date:
        print(f"  ⚠️ {index_name} current_date가 없어 이력 저장 스킵")
        return

    cleaned_history = []
    removed_count = 0

    for entry in history:
        entry_date = normalize_date(entry.get("date"))
        if not entry_date:
            removed_count += 1
            print(f"  ⚠️ {index_name} 잘못된 기존 date 제거: {entry.get('date')}")
            continue

        cleaned_entry = dict(entry)
        cleaned_entry["date"] = entry_date
        cleaned_history.append(cleaned_entry)

    if removed_count:
        print(f"  🧹 {index_name} 잘못된 기존 레코드 {removed_count}건 정리")

    for entry in cleaned_history:
        if entry.get("date") == current_date:
            print(f"  ℹ️ {index_name} {current_date} 데이터 이미 존재. 스킵.")
            indices_data[key] = cleaned_history
            return

    cleaned_history.append(
        {
            "date": current_date,
            "value": new_data["current_value"],
            "crawled_at": new_data["crawled_at"],
        }
    )

    cleaned_history.sort(key=lambda x: x["date"])
    indices_data[key] = cleaned_history
    print(f"  ✅ {index_name} 이력 추가: {current_date} = {new_data['current_value']}")


def main():
    print("=" * 60)
    print("📊 운임지수 크롤링 (SCFI + KCCI)")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    indices_data = load_indices()

    scfi_data = crawl_scfi()
    kcci_data = crawl_kcci()

    update_history(indices_data, scfi_data, "SCFI")
    update_history(indices_data, kcci_data, "KCCI")

    save_indices(indices_data)

    latest = {
        "scfi": scfi_data,
        "kcci": kcci_data,
        "updated_at": datetime.now().isoformat(),
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    latest_path = OUTPUT_DIR / "freight_latest.json"
    with open(latest_path, "w", encoding="utf-8") as f:
        json.dump(latest, f, ensure_ascii=False, indent=2)

    print(f"📦 최신 지수 → {latest_path}")


if __name__ == "__main__":
    main()
