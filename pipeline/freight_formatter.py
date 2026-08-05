"""
운임지수 포맷터 - 텔레그램 표 + 이메일 PNG 차트
─────────────────────────────────────────────────
- 텔레그램: 간결한 텍스트 표
- 이메일: matplotlib PNG 차트 (Outlook 호환)
  당해년도 초록 실선, 전년도 파란 실선
  좌상단: 현재값, 전년동기값, YoY 변동폭

※ 크롤링이 실패해도 저장된 이력(freight_indices.json)으로 차트를 그립니다.
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
    return {}


def format_change(current: float, previous: float) -> str:
    if previous is None or previous == 0:
        return "-"
    diff = current - previous
    pct = (diff / previous) * 100
    if diff > 0:
        return f"▲ {diff:,.0f} (+{pct:.1f}%)"
    elif diff < 0:
        return f"▼ {abs(diff):,.0f} ({pct:.1f}%)"
    return "- (0.0%)"


def has_new_data(latest: dict) -> bool:
    if not latest:
        return False
    for key in ("scfi", "kcci"):
        item = latest.get(key)
        if item and item.get("current_value"):
            return True
    return False


def build_simple_telegram_table(latest: dict) -> str | None:
    if not has_new_data(latest):
        return None

    scfi = latest.get("scfi") or {}
    kcci = latest.get("kcci") or {}

    lines = ["\n📊 <b>주간 운임지수</b>\n"]

    if scfi.get("current_value"):
        chg = format_change(scfi["current_value"], scfi.get("previous_value"))
        prev = scfi.get("previous_value") or 0
        lines.append(f"🚢 <b>SCFI</b>  {scfi['current_value']:,.0f}  (전주 {prev:,.0f})  {chg}")
        if scfi.get("current_date"):
            lines.append(f"    <i>{scfi['current_date']} 기준</i>")

    if kcci.get("current_value"):
        chg = format_change(kcci["current_value"], kcci.get("previous_value"))
        prev = kcci.get("previous_value") or 0
        lines.append(f"🇰🇷 <b>KCCI</b>  {kcci['current_value']:,.0f}  (전주 {prev:,.0f})  {chg}")
        if kcci.get("current_date"):
            lines.append(f"    <i>{kcci['current_date']} 기준</i>")

    return "\n".join(lines)


def chart_week(date_str: str) -> int:
    """차트용 주차 (12월말 ISO week 1 보정)"""
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
    if not current_date or not last_year_data:
        return None
    try:
        cur_week = chart_week(current_date)
        best_match, best_diff = None, 999
        for date_str, val in last_year_data:
            diff = abs(chart_week(date_str) - cur_week)
            if diff < best_diff:
                best_diff, best_match = diff, val
        if best_match is not None and best_diff <= 2:
            return best_match
    except Exception:
        pass
    return None


def resolve_series(latest_item: dict | None, history: list) -> dict:
    """
    차트에 쓸 현재값/전주값/기준일을 결정.
    크롤링 결과(latest)가 있으면 우선, 없으면 이력의 마지막 2건으로 대체.
    """
    if latest_item and latest_item.get("current_value"):
        return {
            "current_value": latest_item.get("current_value"),
            "previous_value": latest_item.get("previous_value"),
            "current_date": latest_item.get("current_date")
                            or (history[-1]["date"] if history else None),
        }

    if history:
        cur = history[-1]
        prev = history[-2] if len(history) > 1 else None
        return {
            "current_value": cur.get("value"),
            "previous_value": prev.get("value") if prev else None,
            "current_date": cur.get("date"),
        }

    return {"current_value": None, "previous_value": None, "current_date": None}


def build_png_chart(index_name: str, history: list, current_val: float = None,
                    previous_val: float = None, current_date: str = None,
                    output_path: str = None) -> str | None:
    """matplotlib PNG 차트 생성 (Outlook 호환)"""
    if not history or len(history) < 2:
        print(f"  ⚠️ {index_name} 이력 부족, 차트 생략")
        return None

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.ticker as ticker
        import matplotlib.font_manager as fm

        font_path = None
        for candidate in [
            "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        ]:
            if Path(candidate).exists():
                font_path = candidate
                break

        if font_path:
            plt.rcParams["font.family"] = fm.FontProperties(fname=font_path).get_name()
        else:
            plt.rcParams["font.family"] = "DejaVu Sans"
        plt.rcParams["axes.unicode_minus"] = False
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

    this_year_weeks = sorted([(chart_week(d), v) for d, v in this_year_data])
    last_year_weeks = sorted([(chart_week(d), v) for d, v in last_year_data])

    yoy_val = find_yoy_value(current_date, last_year_data)

    fig, ax = plt.subplots(figsize=(7, 3.5), dpi=130)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    if last_year_weeks:
        ax.plot([w for w, _ in last_year_weeks], [v for _, v in last_year_weeks],
                color="#1a53a8", linewidth=2, label=str(prev_year), zorder=2)
    if this_year_weeks:
        ax.plot([w for w, _ in this_year_weeks], [v for _, v in this_year_weeks],
                color="#0a8f3f", linewidth=2.5, label=str(current_year), zorder=3)

    ax.grid(True, axis="y", color="#eeeeee", linewidth=0.8)
    ax.set_axisbelow(True)
    ax.set_xlim(1, 53)
    ax.set_xticks([1, 5, 9, 14, 18, 22, 27, 31, 35, 40, 44, 48])
    ax.set_xticklabels(["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
                       fontsize=8, color="#888888")
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, p: f"{x:,.0f}"))
    ax.tick_params(axis="y", labelsize=9, colors="#888888")

    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    for spine in ["bottom", "left"]:
        ax.spines[spine].set_color("#dddddd")

    legend = ax.legend(loc="upper right", fontsize=9, frameon=True,
                       fancybox=True, edgecolor="#dddddd")
    legend.get_frame().set_facecolor("white")

    info_lines = []
    if current_val is not None:
        info_lines.append(f"● 현재  {current_val:,.0f}")
    if yoy_val is not None:
        info_lines.append(f"● 전년동기  {yoy_val:,.0f}")
    if current_val is not None and yoy_val is not None:
        info_lines.append(f"  YoY  {format_change(current_val, yoy_val)}")

    if info_lines:
        ax.text(0.02, 0.97, "\n".join(info_lines), transform=ax.transAxes,
                fontsize=9, verticalalignment="top",
                bbox=dict(boxstyle="round,pad=0.4", facecolor="white",
                          edgecolor="#dddddd", alpha=0.9))

    title_date = f" ({current_date})" if current_date else ""
    ax.set_title(f"{index_name}{title_date}", fontsize=11, fontweight="bold",
                 color="#333333", loc="left", pad=10)

    if output_path is None:
        safe = index_name.lower().replace(" ", "_")
        output_path = str(OUTPUT_DIR / f"chart_{safe}.png")

    plt.tight_layout()
    fig.savefig(output_path, dpi=130, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    print(f"  📊 차트 저장: {output_path}")
    return output_path


def build_email_charts(latest: dict, history: dict) -> list[str]:
    """
    이메일용 PNG 차트 생성 (SCFI, KCCI)
    latest가 비어 있어도 history로 폴백하여 차트를 그립니다.
    """
    latest = latest or {}
    history = history or {}
    chart_paths = []

    targets = [
        ("scfi", "SCFI", "chart_scfi.png"),
        ("kcci", "KCCI", "chart_kcci.png"),
    ]

    for key, label, filename in targets:
        hist = history.get(key, [])
        if not hist:
            print(f"  ⚠️ {label} 이력 없음, 차트 생략")
            continue

        series = resolve_series(latest.get(key), hist)
        if series["current_value"] is None:
            print(f"  ⚠️ {label} 현재값 없음, 차트 생략")
            continue

        path = build_png_chart(
            label,
            hist,
            series["current_value"],
            series["previous_value"],
            series["current_date"],
            str(OUTPUT_DIR / filename),
        )
        if path:
            chart_paths.append(path)

    return chart_paths
