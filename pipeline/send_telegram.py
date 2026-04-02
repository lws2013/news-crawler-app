"""
텔레그램 채널로 물류 뉴스 요약 푸시
─────────────────────────────────────────────────
경영층이 모바일에서 바로 확인할 수 있도록
테마별·영향도별로 정리된 메시지를 전송합니다.

[텔레그램 봇 만드는 법]
1. 텔레그램에서 @BotFather 검색
2. /newbot 입력
3. 봇 이름 입력 (예: SCM물류뉴스봇)
4. 봇 username 입력 (예: scm_logistics_news_bot)
5. 발급받은 토큰 → GitHub Secrets에 TELEGRAM_BOT_TOKEN으로 저장
6. 채널 생성 후 봇을 관리자로 추가
7. 채널 ID → GitHub Secrets에 TELEGRAM_CHAT_ID로 저장
   (채널 ID 확인: 채널에 메시지 보낸 후 
    https://api.telegram.org/bot<TOKEN>/getUpdates 에서 chat.id 확인)
"""

import json
import os
from datetime import datetime
from pathlib import Path

import requests

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

OUTPUT_DIR = Path("pipeline/output")

# 테마별 이모지
THEME_EMOJI = {
    "운송지연_항만적체": "🚢",
    "SHE_규제_위험물": "⚠️",
    "지정학_리스크": "🌍",
    "운임_유가": "💰",
    "기타_물류": "📦",
}


def send_message(text: str, parse_mode: str = "HTML") -> bool:
    """텔레그램 메시지 전송"""
    try:
        resp = requests.post(
            f"{TELEGRAM_API}/sendMessage",
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": text,
                "parse_mode": parse_mode,
                "disable_web_page_preview": True,
            },
            timeout=10,
        )
        resp.raise_for_status()
        return True
    except requests.RequestException as e:
        print(f"❌ 텔레그램 전송 실패: {e}")
        return False


def format_header_message(summary_data: dict) -> str:
    """헤더 메시지 생성"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    total = summary_data.get("total_summaries", 0)

    # 영향도 카운트
    summaries = summary_data.get("summaries", [])
    red = sum(1 for s in summaries if "🔴" in s.get("impact", ""))
    yellow = sum(1 for s in summaries if "🟡" in s.get("impact", ""))
    green = sum(1 for s in summaries if "🟢" in s.get("impact", ""))

    header = (
        f"📰 <b>SCM 물류 뉴스 브리핑</b>\n"
        f"📅 {now}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"총 <b>{total}건</b> | "
        f"🔴 {red} | 🟡 {yellow} | 🟢 {green}\n"
        f"━━━━━━━━━━━━━━━"
    )
    return header


def format_impact_section(summaries: list[dict], impact_filter: str, section_title: str) -> str:
    """영향도별 섹션 메시지 생성"""
    filtered = [s for s in summaries if impact_filter in s.get("impact", "")]

    if not filtered:
        return ""

    lines = [f"\n{section_title}\n"]

    for s in filtered:
        theme_emoji = THEME_EMOJI.get(s.get("theme", ""), "📌")
        title = s.get("title", "제목 없음")
        summary = s.get("summary", "")
        impact_reason = s.get("impact_reason", "")
        action = s.get("action_needed", "")
        url = s.get("url", "")

        block = f"{theme_emoji} <b>{title}</b>\n"
        if summary:
            block += f"   {summary}\n"
        if impact_reason:
            block += f"   💡 {impact_reason}\n"
        if action and action.strip() not in ["-", "없음", "해당없음"]:
            block += f"   🎯 <i>{action}</i>\n"
        if url:
            block += f"   🔗 <a href='{url}'>원문 보기</a>\n"

        lines.append(block)

    return "\n".join(lines)


def main():
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ TELEGRAM_BOT_TOKEN 또는 TELEGRAM_CHAT_ID가 설정되지 않았습니다.")
        print("📖 위 주석의 '텔레그램 봇 만드는 법'을 참고해주세요.")
        return

    # 요약 데이터 로드
    input_path = OUTPUT_DIR / "summary.json"
    if not input_path.exists():
        print(f"❌ {input_path} 파일이 없습니다.")
        return

    with open(input_path, "r", encoding="utf-8") as f:
        summary_data = json.load(f)

    summaries = summary_data.get("summaries", [])

    if not summaries:
        send_message("📰 금일 수집된 물류 뉴스가 없습니다.")
        return

    # ── 1. 헤더 전송 ──
    header = format_header_message(summary_data)
    send_message(header)

    # ── 2. 영향도별 전송 (🔴 → 🟡 → 🟢) ──
    # 텔레그램 메시지 글자수 제한(4096자) 대응: 영향도별로 나눠서 전송

    red_msg = format_impact_section(summaries, "🔴", "🔴 <b>즉시 확인 필요</b>")
    if red_msg:
        send_message(red_msg)

    yellow_msg = format_impact_section(summaries, "🟡", "🟡 <b>모니터링 필요</b>")
    if yellow_msg:
        send_message(yellow_msg)

    green_msg = format_impact_section(summaries, "🟢", "🟢 <b>참고</b>")
    if green_msg:
        # 🟢는 제목만 간략히
        filtered = [s for s in summaries if "🟢" in s.get("impact", "")]
        brief_lines = ["🟢 <b>참고</b>\n"]
        for s in filtered:
            emoji = THEME_EMOJI.get(s.get("theme", ""), "📌")
            brief_lines.append(f"{emoji} {s.get('title', '')}")
        send_message("\n".join(brief_lines))

    print(f"✅ 텔레그램 전송 완료 ({len(summaries)}건)")


if __name__ == "__main__":
    main()
