"""
SCFI & KCCI 운임지수 크롤링 + 이력 관리
─────────────────────────────────────────────────
[SCFI] Shanghai Containerized Freight Index (Playwright)
[KCCI] KOBC Container Composite Index (requests + BeautifulSoup)
  - Comprehensive Index (KCCI)
  - USEC 북미동안 (KUEI, $/FEU)
  - Mediterranean 지중해 (KMDI, $/FEU)

[저장] data/freight_indices.json
  키: scfi / kcci / kcci_usec / kcci_med
"""

import json
import re
from datetime import datetime, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup

OUTPUT_DIR = Path("pipeline/output")
DATA_DIR = Path("data")
INDICES_FILE = DATA_DIR / "freight_indices.json"

DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")

# KCCI에서 수집할 항목: (저장키, Code값, 표시명)
KCCI_TARGETS = [
    ("kcci",      "KCCI", "KCCI Comprehensive Index"),
    ("kcci_usec", "KUEI", "KCCI 북미 동안 항로 (USD/40')"),
    ("kcci_med",  "KMDI", "KCCI 지중해 항로 (USD/40')"),
]


def load_indices() -> dict:
    if INDICES_FILE.exists():
        with open(INDICES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_indices(data: dict):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(INDICES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"💾 지수 이력 저장 → {INDICES_FILE}")


def _to_float(text: str):
    """'8,758' → 8758.0, 실패 시 None"""
    if not text:
        return None
    cleaned = text.strip().replace(",", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


def last_friday(ref: datetime = None) -> str:
    """SCFI 기준일을 못 읽었을 때 사용할 대체값 (직전 금요일)"""
    ref = ref or datetime.now()
    offset = (ref.weekday() - 4) % 7   # 금요일=4
    if offset == 0 and ref.hour < 18:  # 금요일 오전이면 지난주 금요일
        offset = 7
    return (ref - timedelta(days=offset)).strftime("%Y-%m-%d")


def crawl_kcci_all() -> dict:
    """KCCI 페이지에서 Comprehensive + 지정 노선을 한 번에 수집"""
    print("\n🔎 KCCI 크롤링 중...")
    url = "https://www.kobc.or.kr/ebz/shippinginfo/kcci/gridList.do?mId=0304000000"
    results = {}

    try:
        resp = requests.get(url, timeout=15, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        table = soup.find("table")
        if not table:
            print("  ❌ KCCI 테이블을 찾을 수 없습니다.")
            return results

        current_date = None
        previous_date = None
        for th in table.find_all("th"):
            text = th.get_text(" ", strip=True)
            m = DATE_RE.search(text)
            if not m:
                continue
            if "Current" in text:
                current_date = m.group(1)
            elif "Previous" in text:
                previous_date = m.group(1)

        rows = table.find_all("tr")
        for row in rows:
            cells = [c.get_text(" ", strip=True) for c in row.find_all(["td", "th"])]
            if not cells:
                continue

            for key, code, label in KCCI_TARGETS:
                if key in results or code not in cells:
                    continue

                idx = cells.index(code)
                current_val = _to_float(cells[idx + 3]) if idx + 3 < len(cells) else None
                previous_val = _to_float(cells[idx + 4]) if idx + 4 < len(cells) else None

                if current_val is None:
                    nums = [v for v in (_to_float(c) for c in cells[idx + 1:]) if v is not None]
                    if nums:
                        current_val = nums[0]
                        previous_val = nums[1] if len(nums) > 1 else None

                if current_val is not None:
                    results[key] = {
                        "index": label,
                        "code": code,
                        "current_value": current_val,
                        "current_date": current_date,
                        "previous_value": previous_val,
                        "previous_date": previous_date,
                        "crawled_at": datetime.now().isoformat(),
                    }
                    print(f"  ✅ {label}: {current_val:,.0f} ({current_date}), 이전 {previous_val}")

        for key, _, label in KCCI_TARGETS:
            if key not in results:
                print(f"  ⚠️ {label} 수집 실패")

        return results

    except Exception as e:
        print(f"  ❌ KCCI 크롤링 실패: {e}")
        return results


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

            # 1차: 헤더 셀에서 Current/Previous 기준일 탐색
            current_date = None
            previous_date = None
            for cell in page.locator("th, td").all():
                try:
                    text = cell.inner_text().strip()
                except Exception:
                    continue
                if not text or len(text) > 60:
                    continue
                m = DATE_RE.search(text)
                if not m:
                    continue
                if "Current" in text and not current_date:
                    current_date = m.group(1)
                elif "Previous" in text and not previous_date:
                    previous_date = m.group(1)

            # 2차: 페이지 전체 텍스트에서 날짜 수집 (헤더 매칭 실패 시)
            if not current_date:
                body_text = page.inner_text("body")
                dates = sorted(set(DATE_RE.findall(body_text)), reverse=True)
                if dates:
                    current_date = dates[0]
                    previous_date = previous_date or (dates[1] if len(dates) > 1 else None)
                    print(f"  ℹ️ 헤더에서 기준일을 못 읽어 본문에서 추출: {current_date}")

            # 3차: 그래도 없으면 직전 금요일로 대체
            if not current_date:
                current_date = last_friday()
                print(f"  ⚠️ 기준일 추출 실패 → 직전 금요일({current_date})로 대체")

            for row in page.locator("tr").all():
                try:
                    text = row.inner_text().strip()
                except Exception:
                    continue
                if "Comprehensive" not in text:
                    continue

                numbers = []
                for cell in row.locator("td").all():
                    val = _to_float(cell.inner_text())
                    if val is not None and val > 100:
                        numbers.append(val)

                if numbers:
                    browser.close()
                    result = {
                        "index": "SCFI",
                        "current_value": numbers[0],
                        "current_date": current_date,
                        "previous_value": numbers[1] if len(numbers) > 1 else None,
                        "previous_date": previous_date,
                        "crawled_at": datetime.now().isoformat(),
                    }
                    print(f"  ✅ SCFI: {numbers[0]} ({current_date})")
                    return result

            browser.close()
            print("  ❌ SCFI Comprehensive Index를 찾을 수 없습니다.")
            return None

    except Exception as e:
        print(f"  ❌ SCFI 크롤링 실패: {e}")
        return None


def update_history(indices_data: dict, new_data: dict | None, key: str):
    """이력에 새 데이터 추가 (같은 기준일이면 스킵, 날짜 없으면 건너뜀)"""
    if not new_data or not new_data.get("current_value"):
        return

    current_date = new_data.get("current_date")
    if not current_date:
        print(f"  ⚠️ {key} 기준일 없음 → 이력 추가 생략 (차트는 기존 이력 사용)")
        return

    history = indices_data.get(key, [])

    for entry in history:
        if entry.get("date") == current_date:
            print(f"  ℹ️ {key} {current_date} 이미 존재. 스킵.")
            return

    history.append({
        "date": current_date,
        "value": new_data["current_value"],
        "crawled_at": new_data["crawled_at"],
    })
    # 날짜 없는 잔여 항목 제거 후 정렬 (None 비교 오류 방지)
    history = [e for e in history if e.get("date")]
    history.sort(key=lambda x: x["date"])

    indices_data[key] = history
    print(f"  ✅ {key} 이력 추가: {current_date} = {new_data['current_value']:,.0f}")


def main():
    print("=" * 60)
    print("📊 운임지수 크롤링 (SCFI + KCCI)")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    indices_data = load_indices()

    scfi_data = crawl_scfi()
    kcci_results = crawl_kcci_all()

    update_history(indices_data, scfi_data, "scfi")
    for key, _, _ in KCCI_TARGETS:
        update_history(indices_data, kcci_results.get(key), key)

    save_indices(indices_data)

    latest = {
        "scfi": scfi_data,
        "kcci": kcci_results.get("kcci"),
        "kcci_usec": kcci_results.get("kcci_usec"),
        "kcci_med": kcci_results.get("kcci_med"),
        "updated_at": datetime.now().isoformat(),
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    latest_path = OUTPUT_DIR / "freight_latest.json"
    with open(latest_path, "w", encoding="utf-8") as f:
        json.dump(latest, f, ensure_ascii=False, indent=2)
    print(f"📦 최신 지수 → {latest_path}")


if __name__ == "__main__":
    main()
