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


def crawl_kcci() -> dict | None:
    """KCCI 크롤링 (requests + BeautifulSoup)"""
    print("\n🔎 KCCI 크롤링 중...")
    url = "https://www.kobc.or.kr/ebz/shippinginfo/kcci/gridList.do?mId=0304000000"

    try:
        resp = requests.get(url, timeout=15, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
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
            if "Current Index" in h or "CurrentIndex" in h:
                match = re.search(r"(\d{4}-\d{2}-\d{2})", h)
                if match:
                    current_date = match.group(1)
                current_col = i
            elif "Previous Index" in h or "PreviousIndex" in h:
                match = re.search(r"(\d{4}-\d{2}-\d{2})", h)
                if match:
                    previous_date = match.group(1)
                previous_col = i

        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all(["td", "th"])
            cell_texts = [c.get_text(strip=True) for c in cells]

            if "KCCI" in cell_texts:
                current_val = None
                previous_val = None

                if current_col is not None and current_col < len(cell_texts):
                    try:
                        current_val = float(cell_texts[current_col].replace(",", ""))
                    except (ValueError, IndexError):
                        pass
                if previous_col is not None and previous_col < len(cell_texts):
                    try:
                        previous_val = float(cell_texts[previous_col].replace(",", ""))
                    except (ValueError, IndexError):
                        pass

                if not current_val:
                    for c in cell_texts:
                        cleaned = c.replace(",", "").strip()
                        try:
                            val = float(cleaned)
                            if val > 100:
                                if current_val is None:
                                    current_val = val
                                elif previous_val is None and val != current_val:
                                    previous_val = val
                        except ValueError:
                            continue

                if current_val:
                    result = {
                        "index": "KCCI",
                        "current_value": current_val,
                        "current_date": current_date,
                        "previous_value": previous_val,
                        "previous_date": previous_date,
                        "crawled_at": datetime.now().isoformat(),
                    }
                    print(f"  ✅ KCCI: {current_val} ({current_date}), 이전: {previous_val} ({previous_date})")
                    return result

        print("  ❌ KCCI 데이터를 찾을 수 없습니다.")
        return None

    except Exception as e:
        print(f"  ❌ KCCI 크롤링 실패: {e}")
        return None


def crawl_scfi() -> dict | None:
    """SCFI 크롤링 (Playwright - JS 동적 로딩 대응)"""
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

            header_cells = page.locator("th").all()
            current_date = None
            previous_date = None

            for cell in header_cells:
                text = cell.inner_text().strip()
                if "Current Index" in text:
                    match = re.search(r"(\d{4}-\d{2}-\d{2})", text)
                    if match:
                        current_date = match.group(1)
                elif "Previous Index" in text:
                    match = re.search(r"(\d{4}-\d{2}-\d{2})", text)
                    if match:
                        previous_date = match.group(1)

            rows = page.locator("tr").all()
            for row in rows:
                text = row.inner_text().strip()
                if "Comprehensive" in text:
                    cells = row.locator("td").all()
                    numbers = []
                    for cell in cells:
                        cell_text = cell.inner_text().strip().replace(",", "")
                        try:
                            val = float(cell_text)
                            if val > 100:
                                numbers.append(val)
                        except ValueError:
                            continue

                    if numbers:
                        current_val = numbers[0] if len(numbers) > 0 else None
                        previous_val = numbers[1] if len(numbers) > 1 else None

                        browser.close()
                        result = {
                            "index": "SCFI",
                            "current_value": current_val,
                            "current_date": current_date,
                            "previous_value": previous_val,
                            "previous_date": previous_date,
                            "crawled_at": datetime.now().isoformat(),
                        }
                        print(f"  ✅ SCFI: {current_val} ({current_date}), 이전: {previous_val} ({previous_date})")
                        return result

            browser.close()
            print("  ❌ SCFI Comprehensive Index를 찾을 수 없습니다.")
            return None

    except Exception as e:
        print(f"  ❌ SCFI 크롤링 실패: {e}")
        return None


def update_history(indices_data: dict, new_data: dict | None, index_name: str):
    if new_data is None:
        return

    history = indices_data.get(index_name.lower(), [])
    current_date = new_data.get("current_date")

    for entry in history:
        if entry.get("date") == current_date:
            print(f"  ℹ️ {index_name} {current_date} 데이터 이미 존재. 스킵.")
            return

    history.append({
        "date": current_date,
        "value": new_data["current_value"],
        "crawled_at": new_data["crawled_at"],
    })

    history.sort(key=lambda x: x.get("date", ""))
    indices_data[index_name.lower()] = history
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
