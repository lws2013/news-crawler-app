"""
텔레그램 채널로 물류 뉴스 요약 푸시
─────────────────────────────────────────────────
경영층이 모바일에서 바로 확인할 수 있도록
테마별·영향도별로 정리된 메시지를 전송합니다.
긴 메시지는 4,096자 기준으로 자동 분할 전송합니다.
"""

import json
import os
import time
from datetime import datetime
from pathlib import Path

import requests

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

OUTPUT_DIR = Path("pipeline/output")

# 텔레그램 메시지 글자수 제한
MAX_MESSAGE_LENGTH = 4000  # 4096이 한도지만 여유 확보

# 테마별 이모지
THEME_EMOJI = {
    "운송지연_항만적체": "🚢",
    "SHE_규제_위험물": "⚠️",
    "지정학_리스크": "🌍",
    "운임_유가": "💰",
    "기타_물류": "📦",
}


def send_message(text: str, parse_mode: str = "HTML") -> bool:
    """텔레그램 메시지 전송 (단건)"""
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


def send_long_message(text: str):
    """긴 메시지를 자동 분할하여 전송"""
    if len(text) <= MAX_MESSAGE_LENGTH:
        send_message(text)
        return

    # 뉴스 블록 단위로 분할 (\n\n 기준)
    blocks = text.split("\n\n")
    current_chunk = ""

    for block in blocks:
        # 이 블록을 추가해도 제한 이내인지 확인
        test = current_chunk + "\n\n" + block if current_chunk else block

        if len(test) <= MAX_MESSAGE_LENGTH:
            current_chunk = test
        else:
            # 현재까지 모은 걸 전송
            if current_chunk.strip():
                send_message(current_chunk.strip())
                time.sleep(0.5)  # 연속 전송 시 딜레이
            current_chunk = block

    # 마지막 남은 청크 전송
    if current_chunk.strip():
        send_message(current_chunk.strip())


def format_header_message(summary_data: dict) -> str:
    """헤더 메시지 생성"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    total = summary_data.get("total_summaries", 0)

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


def format_news_block(s: dict) -> str:
    """뉴스 1건을 텔레그램 블록으로 포맷"""
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
    if action and action.strip() not in ["-", "없음", "해당없음", ""]:
        block += f"   🎯 <i>{action}</i>\n"
    if url:
        block += f"   🔗 <a href='{url}'>원문 보기</a>"

    return block


def send_impact_section(summaries: list[dict], impact_filter: str, section_title: str):
    """영향도별 섹션을 자동 분할하여 전송"""
    filtered = [s for s in summaries if impact_filter in s.get("impact", "")]

    if not filtered:
        return

    # 섹션 헤더 + 뉴스 블록을 하나씩 쌓으면서 제한 초과 시 전송
    current_chunk = f"\n{section_title}\n"
    chunk_count = 1

    for s in filtered:
        block = format_news_block(s)
        test = current_chunk + "\n" + block

        if len(test) > MAX_MESSAGE_LENGTH:
            # 현재 청크 전송
            if current_chunk.strip():
                send_message(current_chunk.strip())
                time.sleep(0.5)
            # 새 청크 시작 (이어지는 표시)
            chunk_count += 1
            current_chunk = f"{section_title} ({chunk_count})\n\n{block}"
        else:
            current_chunk = test

    # 마지막 청크 전송
    if current_chunk.strip():
        send_message(current_chunk.strip())


def main():
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ TELEGRAM_BOT_TOKEN 또는 TELEGRAM_CHAT_ID가 설정되지 않았습니다.")
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

    sent_count = 0

    # ── 1. 헤더 전송 ──
    header = format_header_message(summary_data)
    send_message(header)
    sent_count += 1

    # ── 2. 영향도별 전송 (🔴 → 🟡 → 🟢) ──
    # 각 섹션 내에서 4,096자 초과 시 자동 분할

    red_items = [s for s in summaries if "🔴" in s.get("impact", "")]
    yellow_items = [s for s in summaries if "🟡" in s.get("impact", "")]
    green_items = [s for s in summaries if "🟢" in s.get("impact", "")]

    if red_items:
        send_impact_section(summaries, "🔴", "🔴 <b>즉시 확인 필요</b>")
        sent_count += len(red_items)

    if yellow_items:
        send_impact_section(summaries, "🟡", "🟡 <b>모니터링 필요</b>")
        sent_count += len(yellow_items)

    if green_items:
        # 🟢는 제목만 간략히 (공간 절약)
        brief_blocks = []
        for s in green_items:
            emoji = THEME_EMOJI.get(s.get("theme", ""), "📌")
            brief_blocks.append(f"{emoji} {s.get('title', '')}")

        brief_text = "🟢 <b>참고</b>\n\n" + "\n".join(brief_blocks)
        send_long_message(brief_text)
        sent_count += len(green_items)

    print(f"✅ 텔레그램 전송 완료 ({sent_count}건)")


if __name__ == "__main__":
    main()
