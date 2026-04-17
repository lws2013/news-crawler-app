"""
Gmail SMTP로 물류 뉴스 브리핑 메일 발송
─────────────────────────────────────────────────
텔레그램과 동일한 요약 내용을 HTML 메일로 발송합니다.
Gmail 앱 비밀번호가 필요합니다.
"""

import json
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
from pathlib import Path

GMAIL_USER = os.environ.get("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
NOTIFY_EMAIL_TO = os.environ.get("NOTIFY_EMAIL_TO", "")

OUTPUT_DIR = Path("pipeline/output")

THEME_EMOJI = {
    "운송지연_항만적체": "🚢",
    "SHE_규제_위험물": "⚠️",
    "지정학_리스크": "🌍",
    "운임_유가": "💰",
    "기타_물류": "📦",
}


def build_html(summary_data: dict) -> str:
    """브리핑 HTML 메일 본문 생성"""
    summaries = summary_data.get("summaries", [])
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    total = summary_data.get("total_summaries", 0)

    red = sum(1 for s in summaries if "🔴" in s.get("impact", ""))
    yellow = sum(1 for s in summaries if "🟡" in s.get("impact", ""))
    green = sum(1 for s in summaries if "🟢" in s.get("impact", ""))

    html = f"""
    <html>
    <head>
    <style>
        body {{ font-family: '맑은 고딕', Arial, sans-serif; color: #333; line-height: 1.6; margin: 0; padding: 0; }}
        .container {{ max-width: 700px; margin: 0 auto; }}
        .header {{ background: #1B3A5C; color: white; padding: 20px 25px; }}
        .header h1 {{ margin: 0; font-size: 20px; }}
        .header .date {{ color: #B0C4DE; font-size: 13px; margin-top: 4px; }}
        .summary {{ background: #F5F7FA; padding: 12px 25px; font-size: 15px; }}
        .summary b {{ font-size: 16px; }}
        .section-title {{ font-size: 15px; font-weight: bold; margin: 20px 25px 8px 25px; padding-bottom: 5px; border-bottom: 2px solid; }}
        .red {{ color: #D32F2F; border-color: #D32F2F; }}
        .yellow {{ color: #F57F17; border-color: #F57F17; }}
        .green {{ color: #388E3C; border-color: #388E3C; }}
        .card {{ border-left: 4px solid; padding: 10px 15px; margin: 8px 25px; background: #FAFAFA; }}
        .card.red {{ border-left-color: #D32F2F; background: #FFF5F5; }}
        .card.yellow {{ border-left-color: #F57F17; background: #FFFBF0; }}
        .card.green {{ border-left-color: #388E3C; background: #F5FFF5; }}
        .card-title {{ font-weight: bold; font-size: 14px; margin-bottom: 4px; }}
        .card-detail {{ font-size: 13px; color: #555; }}
        .card-detail a {{ color: #2E75B6; }}
        .label {{ color: #888; }}
        .highlight {{ color: #D32F2F; font-weight: bold; }}
        .footer {{ padding: 15px 25px; color: #999; font-size: 11px; border-top: 1px solid #E0E0E0; margin-top: 20px; }}
    </style>
    </head>
    <body>
    <div class="container">
    <div class="header">
        <h1>📰 SCM 물류 뉴스 브리핑</h1>
        <div class="date">{now}</div>
    </div>
    <div class="summary">
        총 <b>{total}건</b> &nbsp;|&nbsp;
        🔴 {red} &nbsp;|&nbsp; 🟡 {yellow} &nbsp;|&nbsp; 🟢 {green}
    </div>
    """

    for level, css, title in [
        ("🔴", "red", "🔴 즉시 확인 필요"),
        ("🟡", "yellow", "🟡 모니터링 필요"),
        ("🟢", "green", "🟢 참고"),
    ]:
        items = [s for s in summaries if level in s.get("impact", "")]
        if not items:
            continue

        html += f'<div class="section-title {css}">{title} ({len(items)}건)</div>'

        for s in items:
            emoji = THEME_EMOJI.get(s.get("theme", ""), "📌")
            title_text = s.get("title", "")
            summary_text = s.get("summary", "")
            reason = s.get("impact_reason", "")
            action = s.get("action_needed", "")
            url = s.get("url", "")

            html += f'<div class="card {css}">'
            html += f'<div class="card-title">{emoji} {title_text}</div>'
            html += '<div class="card-detail">'
            if summary_text:
                html += f'{summary_text}<br>'
            if reason:
                html += f'💡 {reason}<br>'
            if action and action.strip() not in ["-", "없음", "해당없음", ""]:
                html += f'🎯 <i>{action}</i><br>'
            if url:
                html += f'🔗 <a href="{url}">원문 보기</a>'
            html += '</div></div>'

    html += """
    <div class="footer">
        본 메일은 SCM 물류 뉴스 AI Agent에 의해 자동 생성·발송되었습니다.<br>
        문의: Global물류팀
    </div>
    </div>
    </body>
    </html>
    """
    return html


def send_email(subject: str, html_body: str, attachment_path: str = None):
    """Gmail SMTP로 메일 발송 (첨부파일 지원)"""
    if not GMAIL_USER or not GMAIL_APP_PASSWORD or not NOTIFY_EMAIL_TO:
        print("❌ Gmail 설정이 없습니다. GMAIL_USER, GMAIL_APP_PASSWORD, NOTIFY_EMAIL_TO를 확인하세요.")
        return

    recipients = [addr.strip() for addr in NOTIFY_EMAIL_TO.split(",")]

    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = f"SCM 물류 브리핑 <{GMAIL_USER}>"
    msg["To"] = ", ".join(recipients)

    msg.attach(MIMEText(html_body, "html", "utf-8"))

    # 첨부파일
    if attachment_path and Path(attachment_path).exists():
        with open(attachment_path, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())
        encoders.encode_base64(part)
        today_str = datetime.now().strftime("%Y%m%d")
        filename = f"scm_news_{today_str}.txt"
        part.add_header("Content-Disposition", "attachment", filename=("utf-8", "", filename))
        msg.attach(part)
        print(f"📎 첨부파일: {filename}")

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.ehlo()
            server.starttls()
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_USER, recipients, msg.as_string())
        print(f"✅ 메일 발송 완료 → {', '.join(recipients)}")
    except Exception as e:
        print(f"❌ 메일 발송 실패: {e}")


def main():
    # 요약 데이터 로드
    input_path = OUTPUT_DIR / "summary.json"
    if not input_path.exists():
        print(f"❌ {input_path} 파일이 없습니다.")
        return

    with open(input_path, "r", encoding="utf-8") as f:
        summary_data = json.load(f)

    summaries = summary_data.get("summaries", [])

    if not summaries:
        print("📰 요약된 뉴스가 없어 메일 미발송.")
        return

    # 제목 생성
    today_str = datetime.now().strftime("%Y.%m.%d")
    red = sum(1 for s in summaries if "🔴" in s.get("impact", ""))
    total = len(summaries)

    if red > 0:
        subject = f"[SCM 물류 브리핑] 🔴 긴급 {red}건 포함 - {today_str}"
    else:
        subject = f"[SCM 물류 브리핑] {total}건 요약 - {today_str}"

    # HTML 생성 및 발송
    html = build_html(summary_data)

    # all_news.json을 txt로 복사하여 첨부
    all_news_path = OUTPUT_DIR / "all_news.json"
    attach_path = OUTPUT_DIR / "all_news.txt"
    if all_news_path.exists():
        import shutil
        shutil.copy(all_news_path, attach_path)

    send_email(subject, html, str(attach_path) if attach_path.exists() else None)


if __name__ == "__main__":
    main()
