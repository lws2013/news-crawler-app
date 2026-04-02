"""
Gemini Flash API로 물류 뉴스 요약·분류·영향도 판단
─────────────────────────────────────────────────
본부장님 요구사항:
- 테마별 분류 (운송지연, SHE규제, 지정학, 운임)
- "우리 영향도" 판단 (🔴높음 / 🟡모니터링 / 🟢낮음)
- 경영층이 바로 읽을 수 있는 요약
"""

import json
import os
import re
import time
from datetime import datetime
from pathlib import Path

import requests

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
OUTPUT_DIR = Path("pipeline/output")

# gemini-2.5-flash (무료 tier)
GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.5-flash:generateContent"
)

SYSTEM_PROMPT = """당신은 배터리/전자부품 제조기업의 SCM 본부 물류 전문 분석가입니다.
아래 물류 뉴스들을 분석하여 JSON 형식으로 응답해주세요.

[분류 테마]
1. 운송지연_항만적체: 해운 지연, 항만 적체, 컨테이너 부족, 선박 스케줄 변경
2. SHE_규제_위험물: 배터리 화재, 위험물 규정, 안전 인허가, 창고 규제
3. 지정학_리스크: 관세, 수출규제, 무역분쟁, 제재
4. 운임_유가: 해상/항공 운임 변동, 유가, 물류비
5. 기타_물류: 위 카테고리에 해당하지 않는 물류 관련 뉴스

[영향도 판단 기준]
- 🔴높음: 즉시 대응 필요. 우리 물류 운영/생산계획에 직접 영향 (예: 주요 항로 중단, 위험물 규정 즉시 변경)
- 🟡모니터링: 향후 영향 가능성. 추이를 지켜봐야 함 (예: 운임 상승 추세, 규제 논의 시작)
- 🟢낮음: 당장 영향 없음. 참고 수준

[출력 형식] - 반드시 아래 JSON 배열만 출력하세요. 다른 텍스트는 포함하지 마세요.
[
  {
    "title": "원문 제목",
    "url": "원문 URL",
    "source": "출처",
    "theme": "테마명",
    "summary": "1~2문장 핵심 요약",
    "impact": "🔴높음 또는 🟡모니터링 또는 🟢낮음",
    "impact_reason": "영향도 판단 근거 1문장",
    "action_needed": "필요한 조치 (해당 시)"
  }
]

중요: 물류와 무관한 뉴스는 제외하세요. JSON 배열만 출력하세요."""


def clean_text(text: str) -> str:
    """base64 이미지 데이터, HTML 태그 등 불필요한 데이터를 제거"""
    if not text:
        return ""

    # base64 이미지 데이터 제거 (data:image/png;base64,... 패턴)
    text = re.sub(r'data:image/[^;]+;base64,[A-Za-z0-9+/=]+', '[이미지]', text)

    # 혹시 남은 매우 긴 base64 문자열 제거 (100자 이상 연속 영숫자)
    text = re.sub(r'[A-Za-z0-9+/=]{100,}', '[데이터 생략]', text)

    # HTML 태그 제거
    text = re.sub(r'<[^>]+>', '', text)

    # 연속 공백/줄바꿈 정리
    text = re.sub(r'\s+', ' ', text).strip()

    return text


def call_gemini(news_text: str) -> str:
    """Gemini Flash API 호출"""
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": SYSTEM_PROMPT},
                    {"text": f"\n[뉴스 데이터]\n{news_text}"},
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 4096,
        },
    }

    resp = requests.post(
        f"{GEMINI_URL}?key={GEMINI_API_KEY}",
        headers=headers,
        json=payload,
        timeout=60,
    )
    if resp.status_code != 200:
        print(f"  🔍 Gemini 응답 코드: {resp.status_code}")
        print(f"  🔍 Gemini 응답 본문: {resp.text[:500]}")
    resp.raise_for_status()

    data = resp.json()
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    return text


def parse_gemini_response(response_text: str) -> list[dict]:
    """Gemini 응답에서 JSON 파싱 (마크다운 코드블록 제거)"""
    cleaned = response_text.strip()

    # ```json ... ``` 블록 제거
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        print(f"  ⚠️ JSON 파싱 실패: {e}")
        print(f"  응답 원문 (처음 500자): {cleaned[:500]}")
        return []


def summarize_news(articles: list[dict]) -> list[dict]:
    """뉴스 목록을 Gemini에 보내 요약·분류"""

    if not articles:
        print("⚠️ 요약할 뉴스가 없습니다.")
        return []

    if not GEMINI_API_KEY:
        print("❌ GEMINI_API_KEY가 설정되지 않았습니다.")
        return []

    # 뉴스를 텍스트로 변환 (base64 등 불필요한 데이터 제거)
    news_lines = []
    for i, a in enumerate(articles, 1):
        title = clean_text(a.get("title", ""))
        line = f"{i}. [{a.get('source', 'unknown')}] {title}"

        if a.get("category"):
            line += f" ({a['category']})"

        # snippet 우선, 없으면 content 앞부분 사용 (300자 제한)
        body = a.get("snippet") or (a.get("content", "")[:300] if a.get("content") else "")
        body = clean_text(body)
        if body:
            line += f"\n   {body}"

        if a.get("url"):
            line += f"\n   URL: {a['url']}"
        if a.get("date"):
            line += f" [{a['date']}]"

        news_lines.append(line)

    # 총 텍스트 크기 확인 (디버깅용)
    total_chars = sum(len(l) for l in news_lines)
    print(f"📝 Gemini에 전송할 텍스트: {total_chars:,}자 ({len(news_lines)}건)")

    # 배치 처리
    # Gemini 무료 tier: 15 RPM, 100만 토큰/일
    BATCH_SIZE = 10
    MAX_RETRIES = 3
    all_summaries = []

    for batch_start in range(0, len(news_lines), BATCH_SIZE):
        batch = news_lines[batch_start:batch_start + BATCH_SIZE]
        batch_text = "\n".join(batch)
        batch_num = batch_start // BATCH_SIZE + 1

        print(f"🤖 Gemini 요약 중... (배치 {batch_num}, {len(batch)}건, {len(batch_text):,}자)")

        # 재시도 로직 (429 Too Many Requests 대응)
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = call_gemini(batch_text)
                summaries = parse_gemini_response(response)
                all_summaries.extend(summaries)
                print(f"  ✅ {len(summaries)}건 요약 완료")
                break
            except requests.exceptions.HTTPError as e:
                if e.response is not None and e.response.status_code == 429:
                    wait_time = 15 * attempt
                    print(f"  ⏳ Rate limit 도달. {wait_time}초 대기 후 재시도 ({attempt}/{MAX_RETRIES})")
                    time.sleep(wait_time)
                else:
                    print(f"  ❌ 배치 {batch_num} 실패: {e}")
                    break
            except Exception as e:
                print(f"  ❌ 배치 {batch_num} 실패: {e}")
                break

        # 배치 사이 대기 (rate limit 예방)
        if batch_start + BATCH_SIZE < len(news_lines):
            print(f"  ⏳ 다음 배치 전 5초 대기...")
            time.sleep(5)

    return all_summaries


def main():
    # 병합된 뉴스 데이터 로드
    input_path = OUTPUT_DIR / "all_news.json"
    if not input_path.exists():
        print(f"❌ {input_path} 파일이 없습니다. merge_news.py를 먼저 실행하세요.")
        return

    with open(input_path, "r", encoding="utf-8") as f:
        articles = json.load(f)

    print(f"📥 {len(articles)}건 뉴스 로드")

    # 요약 실행
    summaries = summarize_news(articles)

    # 영향도별 정렬 (🔴 → 🟡 → 🟢)
    impact_order = {"🔴높음": 0, "🟡모니터링": 1, "🟢낮음": 2}
    summaries.sort(key=lambda x: impact_order.get(x.get("impact", ""), 99))

    # 저장
    output_path = OUTPUT_DIR / "summary.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "generated_at": datetime.now().isoformat(),
                "total_articles": len(articles),
                "total_summaries": len(summaries),
                "summaries": summaries,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    # 통계 출력
    theme_counts = {}
    impact_counts = {}
    for s in summaries:
        theme = s.get("theme", "기타")
        impact = s.get("impact", "미분류")
        theme_counts[theme] = theme_counts.get(theme, 0) + 1
        impact_counts[impact] = impact_counts.get(impact, 0) + 1

    print(f"\n📊 요약 결과:")
    print(f"  테마별: {theme_counts}")
    print(f"  영향도별: {impact_counts}")
    print(f"📦 요약 데이터 → {output_path}")


if __name__ == "__main__":
    main()
