"""
Gmail SMTP로 물류 뉴스 브리핑 메일 발송
─────────────────────────────────────────────────
- 뉴스 요약 (🔴🟡🟢)
- 운임지수 차트 (PNG 인라인 CID 임베드 - Outlook 호환)
- all_news.txt 첨부
"""

import json
import os
import shutil
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email import encoders
from datetime import datetime
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent))

try:
    from freight_formatter import load_latest, load_history, build_email_charts
    FREIGHT_AVAILABLE = True
except ImportError:
    FREIGHT_AVAILABLE = False
    print("ℹ️ freight_formatter 모듈 없음. 운임지수 차트 생략.")

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


def build_html(summary_data: dict, chart_cids: list[str] = None) -> str:
    """브리핑 HTML 메일 본문 생성 (차트는 CID 이미지로 삽입)"""
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
        .chart-section {{ padding: 10px 25px; }}
        .chart-title {{ font-size: 16px; font-weight: bold; color: #1B3A5C; border-bottom: 2px solid #2E75B6; padding-bottom: 5px; margin-bottom: 10px; }}
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

    # ── 운임지수 차트 (PNG CID 이미지) ──
    if chart_cids:
        html += '<div class="chart-section">'
        html += '<div class="chart-title">📊 주간 운임지수</div>'
        html += '<table cellpadding="0" cellspacing="0" border="0" width="100%"><tr>'
        for cid in chart_cids:
            html += f'<td width="50%" valign="top"><img src="cid:{cid}" style="width:100%;height:auto;" /></td>'
        html += '</tr></table>'
        html += '</div>'

    # ── 뉴스 섹션 ──
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


def send_email(subject: str, html_body: str, chart_paths: list[str] = None,
               chart_cids: list[str] = None, attachment_path: str = None):
    """Gmail SMTP로 메일 발송 (인라인 이미지 + 첨부파일)"""
    if not GMAIL_USER or not GMAIL_APP_PASSWORD or not NOTIFY_EMAIL_TO:
        print("❌ Gmail 설정이 없습니다.")
        return

    recipients = [addr.strip() for addr in NOTIFY_EMAIL_TO.split(",")]

    # mixed > related > alternative 구조 (첨부파일 + 인라인이미지 + HTML)
    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = f"SCM 물류 브리핑 <{GMAIL_USER}>"
    msg["To"] = ", ".join(recipients)

    # related 파트 (HTML + 인라인 이미지)
    msg_related = MIMEMultipart("related")
    msg_related.attach(MIMEText(html_body, "html", "utf-8"))

    # 차트 PNG를 인라인 이미지로 첨부 (CID 방식)
    if chart_paths and chart_cids:
        for path, cid in zip(chart_paths, chart_cids):
            try:
                with open(path, "rb") as f:
                    img = MIMEImage(f.read(), _subtype="png")
                img.add_header("Content-ID", f"<{cid}>")
                img.add_header("Content-Disposition", "inline", filename=Path(path).name)
                msg_related.attach(img)
                print(f"  🖼️ 인라인 이미지: {cid} ({Path(path).name})")
            except Exception as e:
                print(f"  ⚠️ 이미지 첨부 실패 ({path}): {e}")

    msg.attach(msg_related)

    # all_news.txt 첨부
    if attachment_path and Path(attachment_path).exists():
        with open(attachment_path, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())
        encoders.encode_base64(part)
        today_str = datetime.now().strftime("%Y%m%d")
        filename = f"scm_news_{today_str}.txt"
        part.add_header("Content-Disposition", "attachment", filename=("utf-8", "", filename))
        msg.attach(part)
        print(f"  📎 첨부파일: {filename}")

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

    # 운임지수 차트 생성 (PNG)
    chart_paths = []
    chart_cids = []

    if FREIGHT_AVAILABLE:
        try:
            freight_latest = load_latest()
            freight_history = load_history()
            if freight_latest:
                chart_paths = build_email_charts(freight_latest, freight_history)
                chart_cids = [f"chart_{i}" for i in range(len(chart_paths))]
                print(f"📊 운임지수 차트 {len(chart_paths)}개 생성 완료")
        except Exception as e:
            print(f"⚠️ 운임지수 차트 생성 실패: {e}")

    # HTML 생성 (차트 CID 전달)
    html = build_html(summary_data, chart_cids)

    # all_news.txt 첨부 준비
    all_news_path = OUTPUT_DIR / "all_news.json"
    attach_path = OUTPUT_DIR / "all_news.txt"
    if all_news_path.exists():
        shutil.copy(all_news_path, attach_path)

    # 메일 발송
    send_email(
        subject,
        html,
        chart_paths=chart_paths,
        chart_cids=chart_cids,
        attachment_path=str(attach_path) if attach_path.exists() else None,
    )


if __name__ == "__main__":
    main()
