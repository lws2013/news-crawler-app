"""
운임지수 포맷터 - 텔레그램 표 + 이메일 PNG 차트
─────────────────────────────────────────────────
- 텔레그램: 간결한 텍스트 표
- 이메일: matplotlib PNG 차트 (Outlook 호환)
  당해년도 초록 실선, 전년도 파란 실선
  좌상단: 현재값, 전년동기값, YoY 변동폭
"""

import json
from datetime import datetime
from pathlib import Path

OUTPUT_DIR = Path("pipeline/output")
DATA_DIR = Path("data")
INDICES_FILE = DATA_DIR / "freight_indices.json"


def load_latest() -> dict | None:
    latest_path = OUTPUT_DIR / "freight_latest.json"
    if latest_path.exists():
        with open(latest_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def load_history() -> dict:
    if INDICES_FILE.exists():
        with open(INDICES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"scfi": [], "kcci": []}


def format_change(current: float, previous: float) -> str:
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
    if not latest:
        return False
    scfi = latest.get("scfi")
    kcci = latest.get("kcci")
    return (scfi is not None and scfi.get("current_value")) or \
           (kcci is not None and kcci.get("current_value"))


def build_simple_telegram_table(latest: dict) -> str | None:
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


def chart_week(date_str: str) -> int:
    """차트용 주차 계산 (12월말 ISO week 1 보정)"""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        wk = dt.isocalendar()[1]
        if dt.month == 12 and wk == 1:
            return 53
        if dt.month == 1 and wk >= 52:
            return 0
        return wk
    except Exception:
        return 0


def find_yoy_value(current_date: str, last_year_data: list) -> float | None:
    """전년 동기 값 찾기"""
    if not current_date or not last_year_data:
        return None
    try:
        cur_week = chart_week(current_date)
        best_match = None
        best_diff = 999
        for date_str, val in last_year_data:
            wk = chart_week(date_str)
            diff = abs(wk - cur_week)
            if diff < best_diff:
                best_diff = diff
                best_match = val
        if best_match is not None and best_diff <= 2:
            return best_match
    except Exception:
        pass
    return None


def build_png_chart(index_name: str, history: list, current_val: float = None,
                    previous_val: float = None, current_date: str = None,
                    output_path: str = None) -> str | None:
    """
    matplotlib로 PNG 차트 생성 (Outlook 호환)
    - 당해년도: 초록색 실선
    - 전년도: 파란색 실선
    - 좌상단: 현재값, 전년동기값, YoY 변동폭
    반환: 생성된 PNG 파일 경로
    """
    if not history or len(history) < 2:
        print(f"  ⚠️ {index_name} 이력 부족, 차트 생략")
        return None

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.ticker as ticker
    except ImportError:
        print("  ❌ matplotlib가 설치되지 않았습니다.")
        return None

    current_year = datetime.now().year
    prev_year = current_year - 1

    this_year_data = [(e["date"], e["value"]) for e in history
                      if e.get("date", "").startswith(str(current_year))]
    last_year_data = [(e["date"], e["value"]) for e in history
                      if e.get("date", "").startswith(str(prev_year))]

    if not this_year_data and not last_year_data:
        return None

    # 주차 기준으로 변환
    this_year_weeks = sorted([(chart_week(d), v) for d, v in this_year_data], key=lambda x: x[0])
    last_year_weeks = sorted([(chart_week(d), v) for d, v in last_year_data], key=lambda x: x[0])

    # 전년 동기 값
    yoy_val = find_yoy_value(current_date, last_year_data)

    # 차트 생성
    fig, ax = plt.subplots(figsize=(7, 3.5), dpi=130)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    # 전년도 (파란색)
    if last_year_weeks:
        weeks_l = [w for w, _ in last_year_weeks]
        vals_l = [v for _, v in last_year_weeks]
        ax.plot(weeks_l, vals_l, color="#1a53a8", linewidth=2, label=str(prev_year), zorder=2)

    # 당해년도 (초록색)
    if this_year_weeks:
        weeks_t = [w for w, _ in this_year_weeks]
        vals_t = [v for _, v in this_year_weeks]
        ax.plot(weeks_t, vals_t, color="#0a8f3f", linewidth=2.5, label=str(current_year), zorder=3)

    # 그리드
    ax.grid(True, axis="y", color="#eeeeee", linewidth=0.8)
    ax.set_axisbelow(True)

    # X축
    ax.set_xlim(1, 53)
    ax.set_xlabel("")
    month_ticks = [1, 5, 9, 14, 18, 22, 27, 31, 35, 40, 44, 48]
    month_labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    ax.set_xticks(month_ticks)
    ax.set_xticklabels(month_labels, fontsize=8, color="#888888")

    # Y축 포맷
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, p: f"{x:,.0f}"))
    ax.tick_params(axis="y", labelsize=9, colors="#888888")

    # 테두리 제거
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    for spine in ["bottom", "left"]:
        ax.spines[spine].set_color("#dddddd")

    # 범례 (우상단)
    legend = ax.legend(loc="upper right", fontsize=9, frameon=True,
                       fancybox=True, shadow=False, edgecolor="#dddddd")
    legend.get_frame().set_facecolor("white")

    # 좌상단 텍스트: 현재값 + 전년동기 + YoY
    info_lines = []
    if current_val is not None:
        info_lines.append(f"● 현재  {current_val:,.0f}")
    if yoy_val is not None:
        info_lines.append(f"● 전년동기  {yoy_val:,.0f}")
    if current_val is not None and yoy_val is not None:
        chg = format_change(current_val, yoy_val)
        info_lines.append(f"  YoY  {chg}")

    info_text = "\n".join(info_lines)
    if info_text:
        ax.text(0.02, 0.97, info_text, transform=ax.transAxes,
                fontsize=9, verticalalignment="top", fontfamily="monospace",
                bbox=dict(boxstyle="round,pad=0.4", facecolor="white",
                          edgecolor="#dddddd", alpha=0.9))

    # 제목
    title_date = f" ({current_date})" if current_date else ""
    ax.set_title(f"{index_name}{title_date}", fontsize=11, fontweight="bold",
                 color="#333333", loc="left", pad=10)

    # 저장
    if output_path is None:
        safe_name = index_name.lower().replace(" ", "_").replace("(", "").replace(")", "")
        output_path = str(OUTPUT_DIR / f"chart_{safe_name}.png")

    plt.tight_layout()
    fig.savefig(output_path, dpi=130, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    print(f"  📊 차트 저장: {output_path}")
    return output_path


def build_email_charts(latest: dict, history: dict) -> list[str]:
    """
    이메일용 PNG 차트 생성
    반환: 생성된 PNG 파일 경로 리스트
    """
    chart_paths = []

    scfi = latest.get("scfi") or {}
    kcci = latest.get("kcci") or {}

    if scfi.get("current_value"):
        path = build_png_chart(
            "SCFI",
            history.get("scfi", []),
            scfi.get("current_value"),
            scfi.get("previous_value"),
            scfi.get("current_date"),
            str(OUTPUT_DIR / "chart_scfi.png"),
        )
        if path:
            chart_paths.append(path)

    if kcci.get("current_value"):
        path = build_png_chart(
            "KCCI",
            history.get("kcci", []),
            kcci.get("current_value"),
            kcci.get("previous_value"),
            kcci.get("current_date"),
            str(OUTPUT_DIR / "chart_kcci.png"),
        )
        if path:
            chart_paths.append(path)

    return chart_paths
