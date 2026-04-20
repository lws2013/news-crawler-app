"""
SCFI & KCCI 크롤러 (Previous Index 포함 + GitHub 누적 저장 버전)
- SCFI: Comprehensive Index → Current/Previous Index 추출
- KCCI: Code == 'KCCI' 행 → Current/Previous Index 추출
- 결과를 GitHub JSON에 누적 저장 (없으면 시드 데이터로 초기화)

설치:
    pip install playwright requests
    playwright install chromium

환경변수:
    GITHUB_TOKEN   : GitHub Personal Access Token (repo 권한)
    GITHUB_OWNER   : repo 소유자 (개인 계정 또는 org)
    GITHUB_REPO    : repo 이름
"""

import re, json, os, base64
import requests
from datetime import datetime
from playwright.sync_api import sync_playwright

# ── GitHub 설정 ────────────────────────────────
GITHUB_TOKEN  = os.getenv("GITHUB_TOKEN", "")
GITHUB_OWNER  = os.getenv("GITHUB_OWNER", "your-org")
GITHUB_REPO   = os.getenv("GITHUB_REPO",  "scm-logistics-agent")
GITHUB_PATH   = "data/freight_index.json"
GITHUB_BRANCH = "main"

# ── 시드 데이터 (웹검색 기반 SCFI Comprehensive / KCCI 과거 주요값) ──
# 출처: JIFFA 뉴스, UNCTAD, MacroMicro (2026 W13: 1826.77)
SCFI_SEED = [
    {"date": "2024-01-05", "value": 1971.0},
    {"date": "2024-02-02", "value": 2134.0},
    {"date": "2024-03-01", "value": 1943.0},
    {"date": "2024-04-05", "value": 2300.0},
    {"date": "2024-05-03", "value": 2869.0},
    {"date": "2024-06-07", "value": 3949.0},
    {"date": "2024-07-05", "value": 4991.0},
    {"date": "2024-08-23", "value": 4786.0},
    {"date": "2024-09-20", "value": 2592.0},
    {"date": "2024-10-18", "value": 2226.0},
    {"date": "2024-11-15", "value": 2541.0},
    {"date": "2024-12-20", "value": 2946.0},
    {"date": "2025-01-10", "value": 2962.0},
    {"date": "2025-01-17", "value": 2851.0},
    {"date": "2025-01-24", "value": 2440.0},
    {"date": "2025-01-31", "value": 2279.0},
    {"date": "2025-02-07", "value": 2147.0},
    {"date": "2025-02-21", "value": 1805.0},
    {"date": "2025-03-07", "value": 1582.0},
    {"date": "2025-03-28", "value": 1306.0},
    {"date": "2025-04-04", "value": 1318.0},
    {"date": "2025-04-11", "value": 1336.0},
    {"date": "2025-04-25", "value": 1356.0},
    {"date": "2025-05-02", "value": 1316.0},
    {"date": "2025-05-09", "value": 1260.0},
    {"date": "2025-06-06", "value": 1667.0},
    {"date": "2025-06-27", "value": 1835.0},
    {"date": "2025-07-11", "value": 2030.0},
    {"date": "2025-07-25", "value": 2101.0},
    {"date": "2025-08-01", "value": 2099.0},
    {"date": "2025-09-25", "value": 1198.21},
    {"date": "2025-09-30", "value": 1114.52},
    {"date": "2026-03-28", "value": 1706.95},  # MacroMicro W13 Previous
    {"date": "2026-04-04", "value": 1826.77},  # MacroMicro W13 Current (최신)
]

KCCI_SEED = [
    {"date": "2024-01-05", "value": 1450.0},
    {"date": "2024-03-01", "value": 1680.0},
    {"date": "2024-05-03", "value": 2100.0},
    {"date": "2024-07-05", "value": 2800.0},
    {"date": "2024-09-20", "value": 2200.0},
    {"date": "2024-10-07", "value": 1698.0},
    {"date": "2024-10-14", "value": 1719.0},
    {"date": "2024-11-15", "value": 1850.0},
    {"date": "2024-12-20", "value": 2050.0},
    {"date": "2025-01-10", "value": 2300.0},
    {"date": "2025-02-13", "value": 2801.0},
    {"date": "2025-03-07", "value": 2300.0},
    {"date": "2025-04-04", "value": 1900.0},
    {"date": "2025-06-06", "value": 2046.0},
    {"date": "2025-07-11", "value": 2461.0},
    {"date": "2025-09-25", "value": 2407.0},
    {"date": "2025-10-06", "value": 1698.0},
]

# ═══════════════════════════════════════════════
# GitHub I/O
# ═══════════════════════════════════════════════

def _gh_headers():
    return {"Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"}

def load_from_github() -> dict | None:
    if not GITHUB_TOKEN:
        print("⚠️  GITHUB_TOKEN 미설정 → 로컬 모드 (시드 사용)")
        return None
    url = (f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}"
           f"/contents/{GITHUB_PATH}?ref={GITHUB_BRANCH}")
    r = requests.get(url, headers=_gh_headers())
    if r.status_code == 404:
        return None
    if r.status_code != 200:
        print(f"⚠️  GitHub 읽기 오류 {r.status_code}")
        return None
    body = r.json()
    data = json.loads(base64.b64decode(body["content"]).decode())
    data["_sha"] = body["sha"]
    return data

def save_to_github(data: dict):
    if not GITHUB_TOKEN:
        print("⚠️  GITHUB_TOKEN 없음 → GitHub 저장 스킵")
        return
    sha = data.pop("_sha", None)
    content_b64 = base64.b64encode(
        json.dumps(data, ensure_ascii=False, indent=2).encode()
    ).decode()
    url = (f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}"
           f"/contents/{GITHUB_PATH}")
    payload = {
        "message": f"chore: freight index {datetime.now().strftime('%Y-%m-%d')}",
        "content": content_b64,
        "branch":  GITHUB_BRANCH,
    }
    if sha:
        payload["sha"] = sha
    r = requests.put(url, headers=_gh_headers(), json=payload)
    if r.status_code in (200, 201):
        print(f"✅ GitHub 저장 완료 → {GITHUB_PATH}")
    else:
        print(f"❌ GitHub 저장 실패 {r.status_code}: {r.text[:200]}")

def init_store() -> dict:
    data = load_from_github()
    if data is None:
        print("📦 시드 데이터로 스토어 초기화")
        data = {
            "scfi": sorted(SCFI_SEED, key=lambda x: x["date"]),
            "kcci": sorted(KCCI_SEED, key=lambda x: x["date"]),
        }
    return data

def upsert(store: dict, key: str, date: str, value: float) -> bool:
    """날짜 기준 upsert. 신규면 True."""
    if not date or value is None:
        return False
    records = store.setdefault(key, [])
    for rec in records:
        if rec["date"] == date:
            if rec["value"] != value:
                rec["value"] = value
                print(f"  🔄 {key} {date} 갱신 → {value}")
            return False
    records.append({"date": date, "value": value})
    records.sort(key=lambda x: x["date"])
    print(f"  ➕ {key} {date} 추가 → {value}")
    return True

# ═══════════════════════════════════════════════
# 크롤러 헬퍼
# ═══════════════════════════════════════════════

def _find_col(headers: list, pattern: str) -> tuple:
    for i, h in enumerate(headers):
        if re.search(pattern, h.strip(), re.IGNORECASE):
            m = re.search(r"\d{4}[-/]\d{2}[-/]\d{2}", h.strip())
            return i, (m.group(0) if m else None)
    return None, None

def _parse_float(s: str) -> float | None:
    try:
        return float(s.strip().replace(",", ""))
    except Exception:
        return None

# ═══════════════════════════════════════════════
# SCFI 크롤러
# ═══════════════════════════════════════════════

def crawl_scfi() -> dict:
    result = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        print("[SCFI] 접속 중...")
        page.goto("https://en.sse.net.cn/indices/scfinew.jsp")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(3000)

        headers = page.locator("table th").all_inner_texts()
        print(f"[SCFI] 헤더: {headers}")

        cur_col,  cur_date  = _find_col(headers, r"Current\s+Index")
        prev_col, prev_date = _find_col(headers, r"Previous\s+Index")

        if cur_col is None:
            print("[SCFI] ❌ Current Index 컬럼 없음")
            browser.close()
            return result

        for row in page.locator("table tr").all():
            cells = row.locator("td").all_inner_texts()
            if not cells:
                continue
            if re.search(r"Comprehensive\s+Index", cells[0].strip(), re.IGNORECASE):
                result = {
                    "current_date":   cur_date,
                    "current_value":  _parse_float(cells[cur_col])  if cur_col  < len(cells) else None,
                    "previous_date":  prev_date,
                    "previous_value": _parse_float(cells[prev_col]) if prev_col is not None and prev_col < len(cells) else None,
                }
                print(f"[SCFI] ✅ {result}")
                break
        browser.close()
    return result

# ═══════════════════════════════════════════════
# KCCI 크롤러
# ═══════════════════════════════════════════════

def crawl_kcci() -> dict:
    result = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        print("[KCCI] 접속 중...")
        page.goto("https://www.kobc.or.kr/ebz/shippinginfo/kcci/gridList.do?mId=0304000000")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(3000)

        headers = page.locator("table th").all_inner_texts()
        print(f"[KCCI] 헤더: {headers}")

        cur_col,  cur_date  = _find_col(headers, r"Current\s+Index")
        prev_col, prev_date = _find_col(headers, r"Previous\s+Index")

        if cur_col is None:
            print("[KCCI] ❌ Current Index 컬럼 없음")
            browser.close()
            return result

        for row in page.locator("table tr").all():
            cells = row.locator("td").all_inner_texts()
            if len(cells) > 1 and cells[1].strip().upper() == "KCCI":
                result = {
                    "current_date":   cur_date,
                    "current_value":  _parse_float(cells[cur_col])  if cur_col  < len(cells) else None,
                    "previous_date":  prev_date,
                    "previous_value": _parse_float(cells[prev_col]) if prev_col is not None and prev_col < len(cells) else None,
                }
                print(f"[KCCI] ✅ {result}")
                break
        browser.close()
    return result

# ═══════════════════════════════════════════════
# 메인 진입점
# ═══════════════════════════════════════════════

def run() -> dict:
    """
    크롤링 실행 → GitHub 갱신.
    반환: {"scfi": {...}, "kcci": {...}, "store": {...}, "is_new": bool}
    """
    store = init_store()
    is_new = False

    scfi = crawl_scfi()
    kcci = crawl_kcci()

    for key, obj in [("scfi", scfi), ("kcci", kcci)]:
        for field in ["current", "previous"]:
            d = obj.get(f"{field}_date")
            v = obj.get(f"{field}_value")
            is_new = upsert(store, key, d, v) or is_new

    if is_new:
        save_to_github(store)
    else:
        print("ℹ️  신규 데이터 없음 → GitHub 저장 스킵")

    return {"scfi": scfi, "kcci": kcci, "store": store, "is_new": is_new}

if __name__ == "__main__":
    res = run()
    print("\n" + "=" * 60)
    print(f"SCFI : {res['scfi']}")
    print(f"KCCI : {res['kcci']}")
    print(f"신규  : {res['is_new']}")
