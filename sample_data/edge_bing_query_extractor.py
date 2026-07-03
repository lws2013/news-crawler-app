# -*- coding: utf-8 -*-
"""
Microsoft Edge에 열린 Bing 검색 탭들의 검색어를
'왼쪽 탭 -> 오른쪽 탭' 순서대로 추출하여 텍스트 파일 하나로 저장합니다.
(마커 규칙 없음: 검색어를 순서대로 이어 붙입니다.)

실행 환경 : Windows + Microsoft Edge (실행 중이어야 함)
필요 패키지: pip install uiautomation
"""

import os
import sys
import time
import subprocess
import urllib.parse
from datetime import datetime

try:
    import uiautomation as auto
except ImportError:
    print("[오류] 'uiautomation' 라이브러리가 필요합니다.  설치: pip install uiautomation")
    sys.exit(1)

# ---------------------------------------------------------------------------
# 설정
# ---------------------------------------------------------------------------
OUTPUT_BASE = "bing_queries"       # 결과 파일 기본 이름 (뒤에 날짜/시간이 붙습니다)
SEPARATOR = "\n"                   # "\n"=한 줄에 하나,  ""=구분 없이 그냥 붙이기
TAB_SWITCH_DELAY = 0.45            # 탭 전환 후 주소창 갱신 대기(초)
VERBOSE = True                     # 진단 출력

auto.SetGlobalSearchTimeout(2)


# ---------------------------------------------------------------------------
# URL 처리
# ---------------------------------------------------------------------------
def normalize_url(url: str) -> str:
    if not url:
        return ""
    url = url.strip()
    if url.startswith("http://") or url.startswith("https://"):
        return url
    return "https://" + url


def is_bing_search(url: str) -> bool:
    u = normalize_url(url).lower()
    return ("bing.com/search" in u) and ("q=" in u)


def extract_query(url: str):
    u = normalize_url(url)
    parsed = urllib.parse.urlparse(u)
    params = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
    if "q" in params and params["q"]:
        return params["q"][0]
    return None


# ---------------------------------------------------------------------------
# Edge UI 자동화
# ---------------------------------------------------------------------------
def find_edge_windows():
    root = auto.GetRootControl()
    out = []
    for w in root.GetChildren():
        name = w.Name or ""
        cls = w.ClassName or ""
        if cls == "Chrome_WidgetWin_1" and "edge" in name.lower():
            out.append(w)
        if VERBOSE and cls == "Chrome_WidgetWin_1":
            print(f"   (창) class={cls!r} name={name[:45]!r}")
    return out


def get_tab_items(window):
    """창 전체를 훑어 TabItemControl을 모두 모으고 좌->우(또는 위->아래)로 정렬."""
    items = []

    def walk(ctrl, depth):
        if depth > 18:
            return
        try:
            children = ctrl.GetChildren()
        except Exception:
            return
        for ch in children:
            ctn = ch.ControlTypeName
            if ctn == "DocumentControl":
                continue  # 웹 페이지 내부는 스킵
            if ctn == "TabItemControl":
                items.append(ch)
                continue  # 탭 안쪽은 더 안 들어감
            walk(ch, depth + 1)

    walk(window, 0)

    def keyf(t):
        try:
            r = t.BoundingRectangle
            return (r.left, r.top)
        except Exception:
            return (0, 0)

    items.sort(key=keyf)
    return items


def dump_structure(window, max_depth=5, max_children=14, cap=220):
    """탭을 못 찾았을 때 트리 구조를 보여주는 진단용 덤프."""
    count = [0]

    def walk(ctrl, depth):
        if depth > max_depth or count[0] > cap:
            return
        try:
            children = ctrl.GetChildren()
        except Exception:
            return
        for ch in children[:max_children]:
            count[0] += 1
            name = (ch.Name or "")[:28]
            print("   " + "  " * depth + f"- {ch.ControlTypeName} {name!r}")
            if ch.ControlTypeName != "DocumentControl":
                walk(ch, depth + 1)

    print("   [구조 덤프 시작]")
    walk(window, 0)
    print("   [구조 덤프 끝]")


def get_address_bar(window):
    found = []

    def walk(ctrl, depth):
        if depth > 16 or found:
            return
        try:
            children = ctrl.GetChildren()
        except Exception:
            return
        for ch in children:
            ctn = ch.ControlTypeName
            if ctn == "DocumentControl":
                continue
            if ctn == "EditControl":
                found.append(ch)
                return
            walk(ch, depth + 1)
            if found:
                return

    walk(window, 0)
    return found[0] if found else None


def read_url(addr) -> str:
    try:
        return addr.GetValuePattern().Value or ""
    except Exception:
        return ""


def get_selected_tab(tabs):
    for t in tabs:
        try:
            if t.GetSelectionItemPattern().IsSelected:
                return t
        except Exception:
            pass
    return None


def select_tab(tab):
    try:
        sp = tab.GetSelectionItemPattern()
        sp.Select()
        if sp.IsSelected:
            return
    except Exception:
        pass
    try:
        tab.Click(simulateMove=False)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# 수집
# ---------------------------------------------------------------------------
def collect_queries():
    windows = find_edge_windows()
    if VERBOSE:
        print(f"[진단] Edge 창 {len(windows)}개 발견")
    if not windows:
        print("[오류] 실행 중인 Microsoft Edge 창을 찾지 못했습니다.")
        return []

    collected = []
    seen = []

    for wi, window in enumerate(windows):
        try:
            window.SetActive()
        except Exception:
            pass
        time.sleep(0.3)

        tabs = get_tab_items(window)
        if VERBOSE:
            print(f"[진단] 창 {wi+1}: 탭 {len(tabs)}개")

        if not tabs:
            if VERBOSE:
                dump_structure(window)
            continue

        addr = get_address_bar(window)
        if addr is None:
            print(f"[경고] 창 {wi+1}: 주소창을 찾지 못해 건너뜁니다.")
            continue

        original = get_selected_tab(tabs)

        for ti, tab in enumerate(tabs):
            select_tab(tab)
            time.sleep(TAB_SWITCH_DELAY)
            url = read_url(addr)
            seen.append(url)
            matched = is_bing_search(url)
            if VERBOSE:
                title = (tab.Name or "")[:35]
                print(f"   탭 {ti+1:>2} | bing={'O' if matched else 'X'} | {title!r}")
                print(f"          url={url!r}")
            if matched:
                q = extract_query(url)
                if q is not None:
                    collected.append(q)

        if original is not None:
            select_tab(original)

    if not collected and seen and VERBOSE:
        print("\n[진단] url 은 읽혔지만 Bing 검색으로 인식된 게 없습니다. 위 url 값을 확인하세요.")

    return collected


def main():
    print("Edge에서 Bing 검색 탭을 읽는 중...\n")
    queries = collect_queries()

    if not queries:
        print("\n[알림] 추출된 검색어가 없습니다.")
        return

    text = SEPARATOR.join(queries)

    # 파일명 뒤에 날짜/시간 추가:  연(26) 월(7) 일(03) _ 시분(1300)  ->  26703_1300
    now = datetime.now()
    stamp = f"{now:%y}{now.month}{now:%d}_{now:%H%M}"
    filename = f"{OUTPUT_BASE}_{stamp}.txt"
    filepath = os.path.abspath(filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(text)

    print(f"\n[완료] 총 {len(queries)}개 검색어를 저장했습니다.")
    print(f"        파일: {filepath}")
    print("\n----- 결과 미리보기 -----")
    print(text)

    # 저장한 텍스트 파일 열기.
    # 일부 환경(보안/세션 격리 에이전트)이 파일 '열기' 동작을 가로채 경로를
    # 인코딩해 버리므로, 파일 연결을 우회해 메모장을 직접 실행합니다.
    opened = False
    candidates = [
        ["notepad.exe", filepath],
        [os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "notepad.exe"), filepath],
    ]
    for cmd in candidates:
        try:
            subprocess.Popen(cmd)
            opened = True
            break
        except Exception:
            continue

    if not opened:
        try:
            os.startfile(filepath)   # 마지막 대안 (Windows 전용)
        except Exception as e:
            print(f"(자동 열기 실패 - 위 경로에서 직접 열어주세요: {e})")


if __name__ == "__main__":
    main()
