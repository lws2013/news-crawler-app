"""
운임지수 포맷터 - 텔레그램 표 + 이메일 HTML 차트
─────────────────────────────────────────────────
crawl_freight_indices.py가 생성한 freight_latest.json과
freight_indices.json을 읽어서:
1. 텔레그램용 표 텍스트 생성
2. 이메일용 HTML 인라인 차트 생성 (SVG)
"""

import json
from datetime import datetime
from pathlib import Path

OUTPUT_DIR = Path("pipeline/output")
DATA_DIR = Path("data")
INDICES_FILE = DATA_DIR / "freight_indices.json"
LATEST_FILE = OUTPUT_DIR / "freight_latest.json"


def load_latest() -> dict | None:
    """최신 크롤링 데이터 로드"""
    if LATEST_FILE.exists():
        with open(LATEST_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def load_history() -> dict:
    """이력 데이터 로드"""
    if INDICES_FILE.exists():
        with open(INDICES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"scfi": [], "kcci": []}


def format_change(current: float, previous: float) -> str:
    """변동폭 포맷 (▲▼)"""
    if previous is None or previous == 0:
        return "-"
    diff = current - previous
    pct = (diff / previous) * 100
    if diff > 0:
        return f"▲ {diff:,.0f} (+{pct:.1f}%)"
    elif diff < 0:
        return f"▼ {abs(diff):,.0f} ({pct:.1f}%)"
    else:
        return "- (0.0%)"


def has_new_data(latest: dict) -> bool:
    """갱신된 데이터가 있는지 확인"""
    if not latest:
        return False
    scfi = latest.get("scfi")
    kcci = latest.get("kcci")
    return (scfi is not None and scfi.get("current_value")) or \
           (kcci is not None and kcci.get("current_value"))


def build_telegram_table(latest: dict) -> str | None:
    """텔레그램용 운임지수 표 생성 (HTML 포맷)"""
    if not has_new_data(latest):
        return None

    scfi = latest.get("scfi") or {}
    kcci = latest.get("kcci") or {}

    lines = [
        "\n📊 <b>주간 운임지수</b>\n",
        "┌──────┬──────┬──────┬──────────┐",
        "│ 지수     │ 금주     │ 전주     │ 변동폭              │",
        "├──────┼──────┼──────┼──────────┤",
    ]

    if scfi.get("current_value"):
        s_cur = f"{scfi['current_value']:,.0f}"
        s_prev = f"{scfi.get('previous_value', 0):,.0f}" if scfi.get("previous_value") else "-"
        s_chg = format_change(scfi["current_value"], scfi.get("previous_value"))
        lines.append(f"│ SCFI  │ {s_cur:>6} │ {s_prev:>6} │ {s_chg:>10} │")

    if kcci.get("current_value"):
        k_cur = f"{kcci['current_value']:,.0f}"
        k_prev = f"{kcci.get('previous_value', 0):,.0f}" if kcci.get("previous_value") else "-"
        k_chg = format_change(kcci["current_value"], kcci.get("previous_value"))
        if scfi.get("current_value"):
            lines.append("├──────┼──────┼──────┼──────────┤")
        lines.append(f"│ KCCI  │ {k_cur:>6} │ {k_prev:>6} │ {k_chg:>10} │")

    lines.append("└──────┴──────┴──────┴──────────┘")

    # 기준일
    dates = []
    if scfi.get("current_date"):
        dates.append(f"SCFI: {scfi['current_date']}")
    if kcci.get("current_date"):
        dates.append(f"KCCI: {kcci['current_date']}")
    if dates:
        lines.append(f"<i>기준: {', '.join(dates)}</i>")

    return "\n".join(lines)


def build_simple_telegram_table(latest: dict) -> str | None:
    """텔레그램용 간결한 운임지수 표"""
    if not has_new_data(latest):
        return None

    scfi = latest.get("scfi") or {}
    kcci = latest.get("kcci") or {}

    lines = ["\n📊 <b>주간 운임지수</b>\n"]

    if scfi.get("current_value"):
        s_chg = format_change(scfi["current_value"], scfi.get("previous_value"))
        lines.append(f"🚢 <b>SCFI</b>  {scfi['current_value']:,.0f}  (전주 {scfi.get('previous_value', 0):,.0f})  {s_chg}")
        if scfi.get("current_date"):
            lines.append(f"    <i>{scfi['current_date']} 기준</i>")

    if kcci.get("current_value"):
        k_chg = format_change(kcci["current_value"], kcci.get("previous_value"))
        lines.append(f"🇰🇷 <b>KCCI</b>  {kcci['current_value']:,.0f}  (전주 {kcci.get('previous_value', 0):,.0f})  {k_chg}")
        if kcci.get("current_date"):
            lines.append(f"    <i>{kcci['current_date']} 기준</i>")

    return "\n".join(lines)


def build_svg_chart(index_name: str, history: list, current_val: float = None,
                    previous_val: float = None, current_date: str = None) -> str:
    """
    SVG 인라인 차트 생성
    - 당해년도: 초록색 실선
    - 전년도: 파란색 실선
    - 좌상단: 금주/전주 값 + 변동폭
    """
    if not history or len(history) < 2:
        return f"<p><i>{index_name} 이력 데이터 부족 (차트 생성 불가)</i></p>"

    current_year = datetime.now().year
    prev_year = current_year - 1

    # 연도별 분리
    this_year_data = [(e["date"], e["value"]) for e in history
                      if e.get("date", "").startswith(str(current_year))]
    last_year_data = [(e["date"], e["value"]) for e in history
                      if e.get("date", "").startswith(str(prev_year))]

    if not this_year_data and not last_year_data:
        return f"<p><i>{index_name} 차트 데이터 없음</i></p>"

    # 차트 크기
    w, h = 500, 250
    pad_left, pad_right, pad_top, pad_bottom = 60, 20, 60, 30

    chart_w = w - pad_left - pad_right
    chart_h = h - pad_top - pad_bottom

    # Y축 범위
    all_values = [v for _, v in this_year_data + last_year_data]
    if current_val:
        all_values.append(current_val)
    if previous_val:
        all_values.append(previous_val)

    y_min = min(all_values) * 0.9
    y_max = max(all_values) * 1.1

    def week_of_year(date_str: str) -> int:
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            return dt.isocalendar()[1]
        except:
            return 0

    def y_pos(val: float) -> float:
        if y_max == y_min:
            return pad_top + chart_h / 2
        return pad_top + chart_h - (val - y_min) / (y_max - y_min) * chart_h

    def x_pos(week: int) -> float:
        return pad_left + (week - 1) / 52 * chart_w

    # SVG 시작
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" style="max-width:500px;width:100%;background:#fff;border:1px solid #e0e0e0;border-radius:8px;margin:10px 0;">'

    # Y축 그리드
    y_steps = 5
    for i in range(y_steps + 1):
        val = y_min + (y_max - y_min) * i / y_steps
        y = y_pos(val)
        svg += f'<line x1="{pad_left}" y1="{y:.0f}" x2="{w - pad_right}" y2="{y:.0f}" stroke="#eee" stroke-width="1"/>'
        svg += f'<text x="{pad_left - 5}" y="{y:.0f}" text-anchor="end" font-size="10" fill="#888" dominant-baseline="middle">{val:,.0f}</text>'

    # 전년도 선 (파란색)
    if last_year_data:
        points = []
        for date_str, val in sorted(last_year_data, key=lambda x: x[0]):
            wk = week_of_year(date_str)
            points.append(f"{x_pos(wk):.1f},{y_pos(val):.1f}")
        if points:
            svg += f'<polyline points="{" ".join(points)}" fill="none" stroke="#4285F4" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>'

    # 당해년도 선 (초록색)
    if this_year_data:
        points = []
        for date_str, val in sorted(this_year_data, key=lambda x: x[0]):
            wk = week_of_year(date_str)
            points.append(f"{x_pos(wk):.1f},{y_pos(val):.1f}")
        if points:
            svg += f'<polyline points="{" ".join(points)}" fill="none" stroke="#0ECB81" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>'

    # 전년 동기 값 찾기
    yoy_val = None
    if current_date and last_year_data:
        try:
            cur_dt = datetime.strptime(current_date, "%Y-%m-%d")
            cur_week = cur_dt.isocalendar()[1]
            # 전년도 데이터에서 같은 주차 또는 가장 가까운 주차 찾기
            best_match = None
            best_diff = 999
            for date_str, val in last_year_data:
                try:
                    wk = datetime.strptime(date_str, "%Y-%m-%d").isocalendar()[1]
                    diff = abs(wk - cur_week)
                    if diff < best_diff:
                        best_diff = diff
                        best_match = val
                except:
                    continue
            if best_match and best_diff <= 2:
                yoy_val = best_match
        except:
            pass

    # 범례 + 현재값 (좌상단)
    legend_y = 18
    svg += f'<circle cx="{pad_left + 5}" cy="{legend_y}" r="5" fill="#0ECB81"/>'
    cur_text = f"현재 {current_val:,.0f}" if current_val else "현재 -"
    svg += f'<text x="{pad_left + 15}" y="{legend_y + 4}" font-size="12" font-weight="bold" fill="#333">{cur_text}</text>'

    svg += f'<circle cx="{pad_left + 130}" cy="{legend_y}" r="5" fill="#4285F4"/>'
    yoy_text = f"전년동기 {yoy_val:,.0f}" if yoy_val else "전년동기 -"
    svg += f'<text x="{pad_left + 140}" y="{legend_y + 4}" font-size="12" font-weight="bold" fill="#333">{yoy_text}</text>'

    # 전년 동기 대비 변동폭
    if current_val and yoy_val:
        chg = format_change(current_val, yoy_val)
        color = "#D32F2F" if current_val > yoy_val else "#388E3C" if current_val < yoy_val else "#888"
        svg += f'<text x="{w - pad_right}" y="{legend_y + 4}" text-anchor="end" font-size="13" font-weight="bold" fill="{color}">YoY {chg}</text>'

    # 제목
    svg += f'<text x="{pad_left}" y="{legend_y + 22}" font-size="11" fill="#888">{index_name} ({current_date or ""})</text>'

    # 연도 범례
    svg += f'<text x="{w - pad_right}" y="{legend_y + 22}" text-anchor="end" font-size="10" fill="#888">'
    svg += f'<tspan fill="#0ECB81">● {current_year}</tspan>  <tspan fill="#4285F4">● {prev_year}</tspan></text>'

    svg += '</svg>'
    return svg


def build_email_charts(latest: dict, history: dict) -> str:
    """이메일 HTML에 삽입할 운임지수 차트 생성"""
    html = '<div style="margin: 20px 0;">'
    html += '<h2 style="color:#1B3A5C;font-size:18px;border-bottom:2px solid #2E75B6;padding-bottom:5px;">📊 주간 운임지수</h2>'

    scfi = latest.get("scfi") or {}
    kcci = latest.get("kcci") or {}

    if scfi.get("current_value"):
        html += build_svg_chart(
            "SCFI (Shanghai Containerized Freight Index)",
            history.get("scfi", []),
            scfi.get("current_value"),
            scfi.get("previous_value"),
            scfi.get("current_date"),
        )

    if kcci.get("current_value"):
        html += build_svg_chart(
            "KCCI (KOBC Container Composite Index)",
            history.get("kcci", []),
            kcci.get("current_value"),
            kcci.get("previous_value"),
            kcci.get("current_date"),
        )

    html += '</div>'
    return html
