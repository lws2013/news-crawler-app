"""
SCFI & KCCI 운임지수 크롤링 + 이력 관리
─────────────────────────────────────────────────
[SCFI] Shanghai Containerized Freight Index - 매주 금요일 갱신
  소스: https://en.sse.net.cn/indices/scfinew.jsp

[KCCI] KOBC Container Composite Index - 매주 월요일 갱신
  소스: https://www.kobc.or.kr/ebz/shippinginfo/kcci/gridList.do

[데이터 저장] data/freight_indices.json (GitHub repo에 커밋)
  - 주차별 SCFI/KCCI 값 누적
  - 전년도 데이터도 보관 (YoY 차트용)
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
    """이력 데이터 로드"""
    if INDICES_FILE.exists():
        with open(INDICES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"scfi": [], "kcci": []}


def save_indices(data: dict):
    """이력 데이터 저장"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(INDICES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"💾 지수 이력 저장 → {INDICES_FILE}")


def crawl_kcci() -> dict | None:
    """KCCI 크롤링 (requests + BeautifulSoup, JS 불필요)"""
    print("\n🔎 KCCI 크롤링 중...")
    url = "https://www.kobc.or.kr/ebz/shippinginfo/kcci/gridList.do?mId=0304000000"

    try:
        resp = requests.get(url, timeout=15, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # 테이블 찾기
        table = soup.find("table")
        if not table:
            print("  ❌ KCCI 테이블을 찾을 수 없습니다.")
            return None

        # 헤더에서 날짜 추출
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

        # KCCI 행 찾기
        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all(["td", "th"])
            cell_texts = [c.get_text(strip=True) for c in cells]

            # Code 컬럼에서 KCCI 찾기
            if "KCCI" in cell_texts:
                kcci_idx = cell_texts.index("KCCI")

                # Current/Previous 값 추출
                current_val = None
                previous_val = None

                for c in cell_texts:
                    # 숫자값 찾기 (콤마 포함)
                    cleaned = c.replace(",", "").strip()
                    try:
                        val = float(cleaned)
                        if val > 100:  # 지수값은 보통 1000 이상
                            if current_val is None:
                                current_val = val
                            elif previous_val is None and val != current_val:
                                previous_val = val
                    except ValueError:
                        continue

                # 더 정확한 방법: 컬럼 인덱스로 추출
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
    """SCFI 크롤링 (requests + BeautifulSoup)"""
    print("\n🔎 SCFI 크롤링 중...")
    url = "https://en.sse.net.cn/indices/scfinew.jsp"

    try:
        resp = requests.get(url, timeout=15, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # 테이블 찾기
        tables = soup.find_all("table")

        for table in tables:
            headers = [th.get_text(strip=True) for th in table.find_all("th")]
            header_text = " ".join(headers)

            # SCFI 테이블 식별
            if "Current Index" not in header_text and "CurrentIndex" not in header_text:
                continue

            # 날짜 추출
            current_date = None
            previous_date = None

            for h in headers:
                if "Current" in h:
                    match = re.search(r"(\d{4}-\d{2}-\d{2})", h)
                    if match:
                        current_date = match.group(1)
                elif "Previous" in h:
                    match = re.search(r"(\d{4}-\d{2}-\d{2})", h)
                    if match:
                        previous_date = match.group(1)

            # Comprehensive Index 행 찾기
            rows = table.find_all("tr")
            for row in rows:
                cells = row.find_all(["td", "th"])
                cell_texts = [c.get_text(strip=True) for c in cells]
                row_text = " ".join(cell_texts)

                if "Comprehensive" in row_text:
                    # 숫자값 추출
                    numbers = []
                    for c in cell_texts:
                        cleaned = c.replace(",", "").strip()
                        try:
                            val = float(cleaned)
                            if val > 100:
                                numbers.append(val)
                        except ValueError:
                            continue

                    if numbers:
                        current_val = numbers[0] if len(numbers) > 0 else None
                        previous_val = numbers[1] if len(numbers) > 1 else None

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

        # JS 동적 로딩으로 테이블이 없는 경우
        print("  ⚠️ SCFI 테이블이 HTML에 없습니다 (JS 동적 로딩).")
        print("  ⚠️ Playwright가 필요할 수 있습니다. 웹검색으로 대체합니다.")
        return crawl_scfi_fallback()

    except Exception as e:
        print(f"  ❌ SCFI 크롤링 실패: {e}")
        return crawl_scfi_fallback()


def crawl_scfi_fallback() -> dict | None:
    """SCFI 대체 크롤링 - container-news.com에서 최신 SCFI 가져오기"""
    print("  🔄 SCFI 대체 소스 시도 (container-news.com)...")
    try:
        resp = requests.get(
            "https://container-news.com/scfi/",
            timeout=15,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # 테이블에서 Composite/Comprehensive 행 찾기
        tables = soup.find_all("table")
        for table in tables:
            rows = table.find_all("tr")
            for row in rows:
                cells = row.find_all(["td", "th"])
                cell_texts = [c.get_text(strip=True) for c in cells]
                row_text = " ".join(cell_texts).lower()

                if "composite" in row_text or "comprehensive" in row_text:
                    numbers = []
                    for c in cell_texts:
                        cleaned = c.replace(",", "").strip()
                        try:
                            val = float(cleaned)
                            if val > 100:
                                numbers.append(val)
                        except ValueError:
                            continue

                    if numbers:
                        result = {
                            "index": "SCFI",
                            "current_value": numbers[0],
                            "current_date": datetime.now().strftime("%Y-%m-%d"),
                            "previous_value": numbers[1] if len(numbers) > 1 else None,
                            "previous_date": None,
                            "crawled_at": datetime.now().isoformat(),
                            "source": "container-news.com",
                        }
                        print(f"  ✅ SCFI (대체): {numbers[0]}")
                        return result

        print("  ❌ SCFI 대체 소스에서도 데이터를 찾을 수 없습니다.")
        return None

    except Exception as e:
        print(f"  ❌ SCFI 대체 크롤링 실패: {e}")
        return None


def update_history(indices_data: dict, new_data: dict | None, index_name: str):
    """이력에 새 데이터 추가 (중복 방지)"""
    if new_data is None:
        return

    history = indices_data.get(index_name.lower(), [])

    # 같은 날짜 데이터가 이미 있는지 확인
    current_date = new_data.get("current_date")
    for entry in history:
        if entry.get("date") == current_date:
            print(f"  ℹ️ {index_name} {current_date} 데이터 이미 존재. 스킵.")
            return

    # 새 엔트리 추가
    history.append({
        "date": current_date,
        "value": new_data["current_value"],
        "crawled_at": new_data["crawled_at"],
    })

    # 날짜 순 정렬
    history.sort(key=lambda x: x.get("date", ""))

    indices_data[index_name.lower()] = history
    print(f"  ✅ {index_name} 이력 추가: {current_date} = {new_data['current_value']}")


def main():
    print("=" * 60)
    print("📊 운임지수 크롤링 (SCFI + KCCI)")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    # 이력 로드
    indices_data = load_indices()

    # SCFI 크롤링
    scfi_data = crawl_scfi()

    # KCCI 크롤링
    kcci_data = crawl_kcci()

    # 이력 업데이트
    update_history(indices_data, scfi_data, "SCFI")
    update_history(indices_data, kcci_data, "KCCI")

    # 이력 저장
    save_indices(indices_data)

    # 최신 데이터를 별도 파일로 저장 (텔레그램/이메일에서 사용)
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
