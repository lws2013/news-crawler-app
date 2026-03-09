from pathlib import Path
from typing import Any
import json
import os
import csv
from html import escape

from openai import OpenAI

PROJECT_ROOT = Path(__file__).resolve().parents[3]

SITE_CONTEXT = """
당사 생산거점:
- KOREA_SEOSAN: 한국 서산, inbound 원자재 및 부품 수입 중요
- HUNGARY_KOMAROM: 헝가리 코마롬, 동아시아발 유럽 inbound 해상/항공 자재 영향 중요
- HUNGARY_IVANCSA: 헝가리 이반차, 동아시아발 유럽 inbound 해상/항공 자재 영향 중요
- USA_GEORGIA: 미국 조지아, 동아시아발 미주 inbound 자재/완제품 영향 중요

거점별 기본 해석 원칙:
- KOREA_SEOSAN:
  한국 inbound 원자재/부품 중심으로 해석
- HUNGARY_KOMAROM / HUNGARY_IVANCSA:
  동아시아 → 유럽 inbound, 수에즈/희망봉/유럽 항만 영향 중심 해석
- USA_GEORGIA:
  동아시아 → 미국 inbound, 북미 항만/철도/트럭 영향 중심 해석
""".strip()


def load_latest_crawled_articles() -> list[dict[str, Any]]:
    data_dir = PROJECT_ROOT / "backend" / "data"

    if not data_dir.exists():
        return []

    json_files = sorted(
        data_dir.glob("*.json"),
        key=lambda x: x.stat().st_mtime,
        reverse=True,
    )
    if not json_files:
        return []

    latest_file = json_files[0]

    with open(latest_file, "r", encoding="utf-8") as f:
        return json.load(f)


def load_poc_shipping_candidates() -> list[dict[str, str]]:
    data_dir = PROJECT_ROOT / "backend" / "data"
    file_path = data_dir / "poc_shipping_risk_candidates.csv"

    if not file_path.exists():
        return []

    rows: list[dict[str, str]] = []
    with open(file_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(dict(row))

    def sort_key(row: dict[str, str]):
        hbl = (row.get("hbl_no") or "").strip()
        row_no = (row.get("row_no") or "").strip()
        return (hbl == "", hbl, row_no)

    rows.sort(key=sort_key)
    return rows


def filter_shipping_rows_by_sites(
    shipping_rows: list[dict[str, str]],
    selected_sites: list[str] | None = None,
) -> list[dict[str, str]]:
    if not selected_sites:
        return shipping_rows

    filtered = []

    for row in shipping_rows:
        pod = (row.get("pod") or "").upper().strip()
        pol = (row.get("pol") or "").upper().strip()
        unloading = (row.get("unloading_place") or "").upper().strip()
        shipper = (row.get("shipper") or "").upper().strip()
        item = ((row.get("item") or "") + " " + (row.get("description") or "")).upper().strip()
        remark = ((row.get("remark") or "") + " " + (row.get("additional_remark") or "")).upper().strip()

        matched = False

        # 헝가리 거점: 유럽 inbound relevance
        if any(site in selected_sites for site in ["HUNGARY_KOMAROM", "HUNGARY_IVANCSA"]):
            if (
                "IVANCSA" in unloading
                or "KOMAROM" in unloading
                or pod.startswith("DE")
                or pod.startswith("HR")
                or pod.startswith("SI")
                or pod.startswith("HU")
                or pod.startswith("NL")
                or pod.startswith("BE")
                or pod.startswith("PL")
            ):
                matched = True

        # 미국 조지아 거점: 미국 inbound relevance
        if "USA_GEORGIA" in selected_sites:
            if (
                "GEORGIA" in unloading
                or pod.startswith("US")
                or "SK BATTERY AMERICA" in shipper
            ):
                matched = True

        # 한국 서산 거점: 한국 inbound 원자재/부품
        if "KOREA_SEOSAN" in selected_sites:
            if (
                "SEOSAN" in unloading
                or pod.startswith("KR")
                or pol.startswith("JP")
                or pol.startswith("CN")
                or pol.startswith("VN")
                or "DG" in remark
                or "BINDER" in item
                or "PVDF" in item
            ):
                matched = True

        if matched:
            filtered.append(row)

    return filtered if filtered else shipping_rows


def _build_articles_text(articles: list[dict[str, Any]], limit: int = 20) -> str:
    article_blocks = []

    for idx, article in enumerate(articles[:limit], start=1):
        source = article.get("source", "unknown")
        title = article.get("title", "")
        date = article.get("date", "")
        url = article.get("url", "")
        content = article.get("content", "") or ""

        if len(content) > 1800:
            content = content[:1800] + "..."

        article_blocks.append(
            f"""
[기사 {idx}]
출처: {source}
발간일: {date}
제목: {title}
링크: {url}
본문:
{content}
""".strip()
        )

    return "\n\n".join(article_blocks)


def _build_shipping_text(shipping_rows: list[dict[str, str]], limit: int = 120) -> str:
    shipping_blocks = []

    for row in shipping_rows[:limit]:
        shipping_blocks.append(
            f"""
[선적후보]
row_no: {row.get("row_no", "")}
shipper: {row.get("shipper", "")}
mbl_no: {row.get("mbl_no", "")}
hbl_no: {row.get("hbl_no", "")}
container_no: {row.get("container_no", "")}
type: {row.get("type", "")}
po: {row.get("po", "")}
qty: {row.get("qty", "")}
unit: {row.get("unit", "")}
item: {row.get("item", "")}
description: {row.get("description", "")}
incoterms: {row.get("incoterms", "")}
vsl: {row.get("vsl", "")}
pol: {row.get("pol", "")}
pod: {row.get("pod", "")}
unloading_place: {row.get("unloading_place", "")}
etd_port: {row.get("etd_port", "")}
etd_po: {row.get("etd_po", "")}
initial_etd: {row.get("initial_etd", "")}
updated_eta: {row.get("updated_eta", "")}
sea_lead: {row.get("sea_lead", "")}
eta_fdest: {row.get("eta_fdest", "")}
eu: {row.get("eu", "")}
by_flag: {row.get("by_flag", "")}
cc: {row.get("cc", "")}
plate_nr: {row.get("plate_nr", "")}
time: {row.get("time", "")}
arrive: {row.get("arrive", "")}
liner: {row.get("liner", "")}
cy: {row.get("cy", "")}
request_dt: {row.get("request_dt", "")}
custom_ref: {row.get("custom_ref", "")}
contract_date: {row.get("contract_date", "")}
drivers_name: {row.get("drivers_name", "")}
remark: {row.get("remark", "")}
additional_remark: {row.get("additional_remark", "")}
risk_reason: {row.get("risk_reason", "")}
risk_level: {row.get("risk_level", "")}
""".strip()
        )

    return "\n\n".join(shipping_blocks)


def build_risk_events_prompt(target_date: str, articles: list[dict[str, Any]]) -> str:
    articles_text = _build_articles_text(articles, limit=40)

    prompt = f"""
너는 글로벌 물류 운영 및 공급망 리스크 분석 전문가다.

너의 임무는 오늘 수집된 물류 뉴스 기사 전체를 읽고,
중복되는 내용을 통합하되 과도하게 뭉치지 않도록
"오늘의 주요 물류 이벤트"를 운영 이벤트 단위로 분리해서 추출하는 것이다.

반드시 아래 원칙을 따른다.

[핵심 원칙]
1. 기사 제목을 나열하지 말고, 실제 물류 운영자가 오늘 점검할 가치가 있는 "운영 이벤트" 단위로 추출하라.
2. 같은 주제 기사라도 영향 경로, 운송모드, 운영 액션이 다르면 별도 이벤트로 분리하라.
3. 하나의 메가 이벤트로 과도하게 통합하지 마라.
4. 단순 참고성/일반 동향성 뉴스는 제외하고, 공급망/해상/항공/내륙/통관/운임에 실질 영향이 있는 것만 남겨라.
5. 심각도는 기사 언급 빈도와 영향 강도를 함께 고려해 HIGH / MEDIUM / LOW로 구분하라.
6. 당사 생산거점과의 관련성을 반드시 평가하라.
7. 출력은 반드시 순수 JSON 배열만 출력하라. 코드블록, 설명문, 머리말, 꼬리말을 쓰지 마라.

{SITE_CONTEXT}

[이벤트 분리 기준]
같은 주제의 기사라도 아래 중 하나가 다르면 별도 이벤트로 분리하라.
1. 영향 운송모드가 다름 (SEA vs AIR vs INLAND)
2. 운영 영향 유형이 다름
   - rerouting / diversion
   - surcharge / rate increase
   - booking stop / capacity shortage
   - congestion / backlog
   - regulation / customs / sanction
3. 실무 대응 액션이 다름
4. 당사 생산거점 relevance가 다름
5. 영향 지역 또는 choke point가 다름

[중요]
중동 관련 기사라도 아래는 하나로 뭉치지 말고 분리 가능하면 분리하라.
- 중동/수에즈/희망봉 우회 리스크
- 중동 항공 허브 차질 및 스페이스 부족
- surcharge / booking stop 확대 리스크
- 유럽 downstream backlog / 항만 혼잡
- 유럽향 해상 리드타임 증가

[당사 거점 relevance 판단 기준]
- KOREA_SEOSAN:
  한국 inbound 원자재/부품 조달, DG/핵심 원자재/단납기 자재 영향 우선
- HUNGARY_KOMAROM:
  동아시아→유럽 inbound 해상/항공, 수에즈/희망봉/유럽 항만 영향 우선
- HUNGARY_IVANCSA:
  동아시아→유럽 inbound 해상/항공, 수에즈/희망봉/유럽 항만 영향 우선
- USA_GEORGIA:
  동아시아→미국 inbound, 북미 항만/철도/트럭/스페이스 영향 우선

[이벤트 추출 시 우선 식별할 주제]
- 중동/호르무즈/홍해/수에즈/희망봉 우회
- 유럽향 해상 리드타임 증가
- 유럽 항만 혼잡 및 backlog
- booking stop / surcharge / rerouting / service diversion
- 항공 허브 차질 / 공역 폐쇄 / capacity reduction / offloading / backlog
- 북미 항만/철도/트럭 병목
- 통관/제재/규제 변화
- 위험물(DG), 냉동/특수 화물 운송 리스크
- 원자재/배터리 밸류체인 조달 영향

[이벤트 객체 생성 규칙]
- event_name은 짧고 명확하게 작성
- summary는 1~2문장으로, "왜 오늘 중요한지" 중심으로 작성
- impact_modes는 반드시 SEA / AIR / INLAND 중 하나 이상 선택
- impact_regions는 실제 지역/항로/권역 중심으로 작성
- impact_keywords는 나중에 선적 후보 필터링에 쓸 수 있게 구체적으로 작성
- relevant_sites는 실제로 연관성 있는 거점만 넣어라
- selection_hint는 사용자가 왜 이 이벤트를 선택해야 하는지 한 줄로 작성
- why_it_matters는 운영자 관점에서 설명하라

[좋은 event_name 예시]
- "중동/수에즈/희망봉 우회 리스크"
- "유럽향 해상 리드타임 증가 리스크"
- "중동 항공 허브 차질 및 스페이스 부족"
- "booking stop 및 surcharge 확대 리스크"
- "유럽 downstream backlog 및 항만 혼잡"
- "북미 최종 ETA 불안정 및 내륙 병목"

[나쁜 event_name 예시]
- "해상 뉴스 요약"
- "항공 시장 동향"
- "유럽 관련 기사"
- "중동 리스크"
- "글로벌 공급망 이슈"

[출력 형식]
반드시 JSON 배열 하나만 출력하라.

[
  {{
    "event_id": "E1",
    "event_name": "",
    "severity": "HIGH|MEDIUM|LOW",
    "summary": "",
    "impact_modes": ["SEA", "AIR", "INLAND"],
    "impact_regions": [],
    "impact_keywords": [],
    "relevant_sites": ["KOREA_SEOSAN", "HUNGARY_KOMAROM", "HUNGARY_IVANCSA", "USA_GEORGIA"],
    "selection_hint": "",
    "why_it_matters": ""
  }}
]

[추가 규칙]
- 최소 3개, 최대 7개의 이벤트를 생성하라.
- 가장 중요한 이벤트부터 순서대로 정렬하라.
- event_id는 E1, E2, E3 순서로 부여하라.
- relevance가 거의 없는 이벤트는 생성하지 마라.
- 기사에서 반복적으로 언급되는 테마는 severity를 높게 평가하라.
- 같은 기사군이라도 아래가 다르면 분리하라:
  - 해상 vs 항공
  - 우회 vs 할증 vs booking stop vs backlog
  - 유럽 영향 vs 미국 영향 vs 한국 영향
- 이벤트 간 구분이 모호할 경우에도, 운영 액션이 다르면 분리하라.

기준일: {target_date}

기사 원문:
{articles_text}
""".strip()

    return prompt


def build_articles_prompt(
    target_date: str,
    articles: list[dict[str, Any]],
    shipping_rows: list[dict[str, str]],
    selected_event_name: str | None = None,
    selected_sites: list[str] | None = None,
) -> str:
    articles_text = _build_articles_text(articles, limit=25)
    shipping_text = _build_shipping_text(shipping_rows, limit=150)

    selected_sites = selected_sites or []
    selected_sites_text = ", ".join(selected_sites) if selected_sites else "전체 거점"
    selected_event_text = selected_event_name or "선택 이벤트 없음(전체 리스크 관점)"

    prompt = f"""
너는 글로벌 물류 운영 및 공급망 리스크 분석 전문가다.

너의 임무는 오늘의 물류 뉴스와 선적 후보 데이터를 함께 검토하여,
선택된 물류 이벤트와 선택된 생산거점 기준으로
"실제로 영향을 받을 가능성이 높은 선적건"을 HBL 단위로 식별하는 것이다.

{SITE_CONTEXT}

[선택된 분석 이벤트]
- {selected_event_text}

[선택된 분석 거점]
- {selected_sites_text}

[강제 분석 지시]
- 반드시 선택된 이벤트를 최우선 기준으로 분석하라.
- 반드시 선택된 생산거점과 직접 관련된 선적건만 우선 선별하라.
- 선택된 생산거점과 관련성이 낮은 HBL은 직접 영향에서 제외하라.
- 선택된 이벤트와 무관한 뉴스 해석은 최소화하라.
- 선택된 생산거점이 다르면 결과도 달라져야 한다.
- HUNGARY_KOMAROM / HUNGARY_IVANCSA 선택 시:
  유럽 inbound, 수에즈/희망봉/유럽향 해상 영향 중심으로 해석하라.
- USA_GEORGIA 선택 시:
  미국 inbound, 북미 항만/철도/트럭/최종 ETA 영향 중심으로 해석하라.
- KOREA_SEOSAN 선택 시:
  한국 inbound 원자재/부품, DG/핵심 자재/납기 민감 자재 영향 중심으로 해석하라.
- 선택된 이벤트와 선택된 생산거점 모두에 관련성이 높은 HBL을 먼저 직접 영향 후보로 제시하라.
- 관련성이 약한 HBL은 간접 영향 또는 모니터링으로 낮춰라.

[가장 중요한 원칙]
1. 선적건 식별은 반드시 HBL_NO 기준으로 한다.
2. 동일 HBL_NO에 속한 여러 행은 하나의 선적건으로 묶어서 종합 판단한다.
3. HBL_NO가 비어 있는 경우에만 row_no를 보조 식별자로 사용한다.
4. 결과는 반드시 HBL_NO 기준으로 정렬한다.
5. 기사와 선적 데이터에 없는 사실은 단정하지 말고, 확실하지 않은 것은 "가능성", "점검 필요", "간접 영향 우려"로 표현하라.
6. 출력은 한국어, 보고서형, 실무자 관점으로 작성하라.

[직접 영향 판단 기준]
- 직접 영향은 "선택된 생산거점의 실제 inbound/outbound 물류 구조와 직접 연결되는 선적건"에 한해 판단하라.
- POD / POL / unloading_place / shipper / item / liner / ETA / request_dt를 함께 보고 판단하라.
- 특정 POD 코드만으로 direct 영향을 단정하지 마라.
- 예를 들어 DEHAM은 독일 Hamburg로 해석하고, 선택 거점이 헝가리일 경우 유럽 inbound relevance를 검토하되,
  한국 서산 또는 미국 조지아와 직접 연결되지 않으면 직접 영향에서 제외하거나 간접 영향으로 낮춰라.
- 선택 거점과 무관한 HBL은 direct에서 제외하라.

[거점별 해석 기준]
- KOREA_SEOSAN:
  한국 inbound 원자재/부품 중심으로 해석한다.
  DG, 핵심 원자재, 납기 민감 자재, 한국향 POD를 우선 본다.
- HUNGARY_KOMAROM / HUNGARY_IVANCSA:
  동아시아 → 유럽 inbound 자재/완제품 영향에 집중한다.
  수에즈, 희망봉 우회, 유럽 항만 혼잡, 유럽향 해상 리드타임 증가와 연결되는 선적을 우선 본다.
- USA_GEORGIA:
  동아시아 → 미국 inbound 자재/완제품 영향에 집중한다.
  북미 항만, 철도, 트럭, 최종 ETA 불안정과 연결되는 선적을 우선 본다.

[분석 우선순위]
1. 선택된 이벤트와 직접 연결되는 항로 / 권역 / 운송모드
2. 선택된 생산거점의 inbound 구조와 직접 연결되는 HBL
3. ETA Fdest / Request dt가 임박한 HBL
4. Remark / Additional Remark에 POD changed, DG, route change, delay, done 등 특이사항이 있는 HBL
5. 기사상 직접 언급된 선사, choke point, hub, route와 연결되는 HBL

[선적 데이터 해석 시 적극 활용할 컬럼]
- HBL_NO: 대표 선적 식별자
- shipper: 공급업체
- po: 구매주문번호
- item / description: 자재/품목 성격
- pol: 선적항
- pod: 도착항
- unloading_place: 내륙 최종 도착지 힌트
- liner: 선사
- vsl: 선박명
- eta_fdest: 최종 도착예정일
- request_dt: 요청일 / 납기 우선순위
- remark / additional_remark: POD changed, DG, DONE 등 특이사항
- risk_reason / risk_level: PoC 사전 판단값

[판단 방식]
- 반드시 "왜 이 HBL이 영향받는지"를 설명하라.
- 단순히 HIGH/MEDIUM/LOW만 쓰지 말고,
  아래 다섯 가지 중 어떤 이유인지 명확히 밝혀라:
  1) 항로 영향(route impact)
  2) 거점 관련성(site relevance)
  3) ETA / Request urgency
  4) liner exposure
  5) remark 특이사항
- 선택된 생산거점과 연관성이 낮은 HBL은 제외하거나 모니터링으로 낮춰라.
- 동일 HBL 안에서 여러 row가 있으면, 가장 높은 리스크와 가장 중요한 근거를 대표로 삼아라.

[문체 및 보고서 스타일 지침]
- 답변은 "뉴스 요약문"이 아니라 "물류운영담당자용 영향도 브리핑 메모"처럼 작성하라.
- 배경 설명을 길게 쓰지 말고, 핵심 판단을 먼저 써라.
- 각 항목은 짧고 단호하게 작성하라.
- 한 항목당 1~2문장을 넘기지 말라.
- 사용자가 바로 스캔할 수 있도록 헤드라인형 문장으로 작성하라.
- 불필요한 서론, 일반론, 반복 설명을 줄여라.
- "왜 중요한지"보다 "무엇이 영향이고 무엇을 봐야 하는지"를 우선하라.

[직접/간접 영향 선적건 작성 규칙]
- 각 HBL은 "한 줄 요약 + 세부 3줄" 구조로 작성하라.
- 한 줄 요약에는 HBL_NO, shipper, po, pol→pod, liner, 영향도를 포함하라.
- 세부 3줄은 반드시 아래 순서를 지켜라:
  - 영향 사유:
  - 거점 관련성:
  - 우선 점검 포인트:
- 같은 표현을 반복하지 말고, HBL별 차이를 드러내라.

[최종 요약 테이블 작성 규칙]
- 표는 실제 업무 보고용 요약본처럼 작성하라.
- "핵심근거"는 길게 쓰지 말고 15~30자 수준으로 압축하라.
- 같은 이유를 반복하지 말고 가장 대표적인 근거만 남겨라.

[출력 형식]
반드시 아래 형식을 그대로 따른다.

1. 핵심 리스크 이벤트
- 오늘 뉴스 기준 핵심 리스크 3~5개를 bullet로 작성
- 형식: [리스크유형] 핵심내용

2. 직접 영향 가능 선적건
- 반드시 HBL_NO 기준으로 정렬
- 각 항목은 아래 형식으로 작성
  - HBL_NO | shipper | po | pol → pod | liner | 영향도
    - 영향 사유:
    - 거점 관련성:
    - 우선 점검 포인트:

3. 간접 영향 가능 선적건
- 반드시 HBL_NO 기준으로 정렬
- 각 항목은 아래 형식으로 작성
  - HBL_NO | shipper | po | pol → pod | liner | 영향도
    - 영향 사유:
    - 거점 관련성:
    - 우선 점검 포인트:

4. 우선 점검 포인트
- 오늘 물류운영담당자가 바로 확인해야 할 점검 포인트를 5~8개 bullet로 작성

5. 권장 대응
- 실무적으로 바로 실행 가능한 액션을 5~8개 bullet로 작성

6. 최종 요약 테이블
- 반드시 HBL_NO 기준으로 정렬
- 아래 형식으로 표처럼 정리
  HBL_NO | row_no_list | shipper | po | pol | pod | liner | eta_fdest | request_dt | 영향도(HIGH/MEDIUM/LOW) | 판단(직접/간접/모니터링) | 핵심근거

[중요 제약]
- 반드시 HBL_NO를 우선 키로 사용하라
- 같은 HBL_NO가 여러 row에 있으면 row_no_list로 묶어라
- HBL_NO가 없는 경우에만 ROW_<row_no> 형식으로 대체 표기하라
- 뉴스와 선적 데이터 둘 다를 근거로 판단하라
- 출력은 한국어로 작성하라
- 보고서형 문체로 간결하고 명확하게 작성하라

기사 원문:
{articles_text}

선적 후보 데이터:
{shipping_text}
""".strip()

    return prompt


def _call_openai(prompt: str) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다.")

    client = OpenAI(api_key=api_key)
    response = client.responses.create(
        model="gpt-5.4",
        input=prompt,
    )
    return response.output_text.strip()


def generate_gemini_text(prompt: str) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY가 설정되지 않았습니다.")

    client = OpenAI(
        api_key=api_key,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    )

    response = client.chat.completions.create(
        model="gemini-3-flash-preview",
        messages=[
            {"role": "system", "content": "You are a helpful logistics risk analysis assistant."},
            {"role": "user", "content": prompt},
        ],
    )

    return response.choices[0].message.content.strip()


def generate_gemini_json(prompt: str) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY가 설정되지 않았습니다.")

    client = OpenAI(
        api_key=api_key,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    )

    response = client.chat.completions.create(
        model="gemini-3-flash-preview",
        messages=[
            {"role": "system", "content": "Return only valid JSON. Do not use markdown code fences."},
            {"role": "user", "content": prompt},
        ],
    )

    return response.choices[0].message.content.strip()


def generate_risk_events(target_date: str, articles: list[dict[str, Any]], llm_model: str) -> list[dict[str, Any]]:
    prompt = build_risk_events_prompt(target_date, articles)

    model_name = (llm_model or "gemini-flash").lower().strip()
    if model_name == "gemini-flash":
        output_text = generate_gemini_json(prompt)
    else:
        output_text = _call_openai(prompt)

    print("\n[DEBUG] raw risk events output:\n", output_text)

    cleaned = output_text.strip()

    if cleaned.startswith("```json"):
        cleaned = cleaned[len("```json"):].strip()
    elif cleaned.startswith("```"):
        cleaned = cleaned[len("```"):].strip()

    if cleaned.endswith("```"):
        cleaned = cleaned[:-3].strip()

    start_idx = cleaned.find("[")
    end_idx = cleaned.rfind("]")
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        cleaned = cleaned[start_idx:end_idx + 1]

    print("\n[DEBUG] cleaned risk events output:\n", cleaned)

    data = json.loads(cleaned)

    if not isinstance(data, list):
        raise ValueError("이벤트 응답이 JSON 배열 형식이 아닙니다.")

    return data


def generate_llm_summary(
    target_date: str,
    articles: list[dict[str, Any]],
    shipping_rows: list[dict[str, str]],
    llm_model: str,
    selected_event_name: str | None = None,
    selected_sites: list[str] | None = None,
) -> str:
    prompt = build_articles_prompt(
        target_date=target_date,
        articles=articles,
        shipping_rows=shipping_rows,
        selected_event_name=selected_event_name,
        selected_sites=selected_sites,
    )

    model_name = (llm_model or "gemini-flash").lower().strip()
    if model_name == "gemini-flash":
        return generate_gemini_text(prompt)

    return _call_openai(prompt)


def build_basic_summary(
    target_date: str,
    articles: list[dict[str, Any]],
    shipping_rows: list[dict[str, str]],
    selected_event_name: str | None = None,
    selected_sites: list[str] | None = None,
) -> str:
    top_articles = articles[:5]
    selected_sites = selected_sites or []

    risk_lines = []
    for article in top_articles:
        source = article.get("source", "unknown")
        title = article.get("title", "제목 없음")
        content = (article.get("content", "") or "").replace("\n", " ").strip()
        preview = content[:120] + ("..." if len(content) > 120 else "")
        risk_lines.append(f"- [{source}] {title}: {preview}")

    grouped: dict[str, list[dict[str, str]]] = {}
    for row in shipping_rows:
        hbl = (row.get("hbl_no") or "").strip()
        row_no = (row.get("row_no") or "").strip()
        key = hbl if hbl else f"ROW_{row_no}"
        grouped.setdefault(key, []).append(row)

    def highest_risk(rows: list[dict[str, str]]) -> str:
        order = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
        best = "LOW"
        best_score = 0
        for r in rows:
            level = (r.get("risk_level") or "LOW").upper().strip()
            score = order.get(level, 1)
            if score > best_score:
                best_score = score
                best = level
        return best

    def collect_unique(rows: list[dict[str, str]], field: str) -> str:
        values = []
        for r in rows:
            v = (r.get(field) or "").strip()
            if v and v not in values:
                values.append(v)
        return ", ".join(values)

    direct_lines = []
    indirect_lines = []
    table_lines = []

    for hbl_key in sorted(grouped.keys()):
        rows = grouped[hbl_key]
        row_no_list = ", ".join(
            [str(r.get("row_no", "")).strip() for r in rows if str(r.get("row_no", "")).strip()]
        )

        shipper = collect_unique(rows, "shipper")
        po = collect_unique(rows, "po")
        pol = collect_unique(rows, "pol")
        pod = collect_unique(rows, "pod")
        liner = collect_unique(rows, "liner")
        unloading = collect_unique(rows, "unloading_place")
        eta_fdest = collect_unique(rows, "eta_fdest")
        request_dt = collect_unique(rows, "request_dt")
        remark = collect_unique(rows, "remark")
        additional_remark = collect_unique(rows, "additional_remark")
        risk_level = highest_risk(rows)

        reason_parts = []
        if pol or pod:
            reason_parts.append(f"Route={pol}->{pod}")
        if liner:
            reason_parts.append(f"Liner={liner}")
        if unloading:
            reason_parts.append(f"Unloading={unloading}")
        if eta_fdest:
            reason_parts.append(f"ETA={eta_fdest}")
        if request_dt:
            reason_parts.append(f"Request={request_dt}")
        if remark:
            reason_parts.append(f"Remark={remark}")
        if additional_remark:
            reason_parts.append(f"AdditionalRemark={additional_remark}")

        reason_text = " / ".join(reason_parts) if reason_parts else "기본 모니터링"

        # fallback에서는 선택 거점 기반으로만 보수적으로 direct 판단
        is_direct = False
        pod_upper = pod.upper()
        unloading_upper = unloading.upper()
        shipper_upper = shipper.upper()

        if any(site in selected_sites for site in ["HUNGARY_KOMAROM", "HUNGARY_IVANCSA"]):
            if (
                "IVANCSA" in unloading_upper
                or "KOMAROM" in unloading_upper
                or pod_upper.startswith("DE")
                or pod_upper.startswith("HR")
                or pod_upper.startswith("SI")
                or pod_upper.startswith("HU")
            ):
                is_direct = True

        if "USA_GEORGIA" in selected_sites:
            if (
                "GEORGIA" in unloading_upper
                or pod_upper.startswith("US")
                or "SK BATTERY AMERICA" in shipper_upper
            ):
                is_direct = True

        if "KOREA_SEOSAN" in selected_sites:
            if (
                "SEOSAN" in unloading_upper
                or pod_upper.startswith("KR")
            ):
                is_direct = True

        if is_direct:
            direct_lines.append(
                f"- {hbl_key} | {shipper} | {po} | {pol} | {pod} | {liner} | {risk_level} | {reason_text}"
            )
            decision = "직접"
        else:
            indirect_lines.append(
                f"- {hbl_key} | {shipper} | {po} | {pol} | {pod} | {liner} | {risk_level} | {reason_text}"
            )
            decision = "간접" if risk_level in {"HIGH", "MEDIUM"} else "모니터링"

        table_lines.append(
            f"{hbl_key} | {row_no_list} | {shipper} | {po} | {pol} | {pod} | {liner} | "
            f"{eta_fdest} | {request_dt} | {risk_level} | {decision} | {reason_text}"
        )

    selected_sites_text = ", ".join(selected_sites) if selected_sites else "전체 거점"
    selected_event_text = selected_event_name or "전체 리스크 관점"

    report_text = f"""
1. 핵심 리스크 이벤트
- 선택 이벤트: {selected_event_text}
- 선택 거점: {selected_sites_text}
{chr(10).join(risk_lines) if risk_lines else '- 핵심 뉴스 없음'}

2. 직접 영향 가능 선적건
{chr(10).join(direct_lines) if direct_lines else '- 현재 fallback 기준에서 직접 영향 확정 후보 없음'}

3. 간접 영향 가능 선적건
{chr(10).join(indirect_lines[:20]) if indirect_lines else '- 간접 영향 후보 없음'}

4. 우선 점검 포인트
- HBL_NO 기준으로 동일 선적건을 묶어서 검토
- 선택 거점 및 선택 이벤트와 관련된 POD/POL을 우선 확인
- Liner가 MAERSK, HAPAG, MSC, CMA 등 관련 공지 가능 선사인지 확인
- ETA Fdest 및 Request dt 임박 건 우선 확인
- Remark / Additional Remark에 POD changed, DG, DONE 등 특이사항 존재 여부 확인

5. 권장 대응
- 선사 및 포워더 공지 업데이트 확인
- ETA 재확인
- route/POD 변경 여부 점검
- DG 화물 별도 점검
- 고객 납기 영향 여부 사전 확인
- 필요 시 대체 운송/우회 가능성 검토

6. 최종 요약 테이블
{chr(10).join(table_lines[:30]) if table_lines else '- 요약 테이블 없음'}
""".strip()

    return report_text


def build_summary_email_payload(target_date: str, llm_model: str = "openai") -> dict[str, str]:
    articles = load_latest_crawled_articles()
    total_count = len(articles)
    model_name = (llm_model or "openai").lower().strip()

    if total_count == 0:
        summary_text = (
            f"물류 뉴스 요약 리포트\n\n"
            f"발간일자 기준: {target_date}\n"
            f"생성 모델: {model_name}\n"
            f"수집된 뉴스가 없습니다."
        )
        html = f"""
        <html>
          <body style="font-family: Arial, sans-serif; color: #222; line-height: 1.7; padding: 24px;">
            <h1 style="font-size: 34px; margin-bottom: 24px;">물류 뉴스 요약 리포트</h1>
            <p><strong>발간일자 기준:</strong> {escape(target_date)}</p>
            <p><strong>생성 모델:</strong> {escape(model_name)}</p>
            <p>수집된 뉴스가 없습니다.</p>
          </body>
        </html>
        """
        return {"summary_text": summary_text, "html": html}

    summary_text = (
        f"물류 뉴스 요약 리포트\n\n"
        f"발간일자 기준: {target_date}\n"
        f"생성 모델: {model_name}\n"
        f"총 {total_count}건의 기사를 바탕으로 작성되었습니다.\n\n"
        f"- 상세 영향 선적 분석은 PoC 리스크 리포트 기능에서 확인하세요."
    )

    html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #222; line-height: 1.7; padding: 24px;">
        <h1 style="font-size: 34px; margin-bottom: 24px;">물류 뉴스 요약 리포트</h1>
        <p><strong>발간일자 기준:</strong> {escape(target_date)}</p>
        <p><strong>생성 모델:</strong> {escape(model_name)}</p>
        <p><strong>총 {total_count}건의 기사</strong>를 바탕으로 작성되었습니다.</p>
        <p>상세 영향 선적 분석은 PoC 리스크 리포트 기능에서 확인하세요.</p>
      </body>
    </html>
    """

    return {"summary_text": summary_text, "html": html}


def build_risk_events_payload(target_date: str, llm_model: str = "gemini-flash") -> dict[str, Any]:
    articles = load_latest_crawled_articles()

    if not articles:
        return {
            "events": [],
            "raw_text": "뉴스 데이터가 없습니다.",
        }

    try:
        events = generate_risk_events(target_date, articles, llm_model)
        print(f"[DEBUG] generated events count = {len(events)}")
        return {
            "events": events,
            "raw_text": json.dumps(events, ensure_ascii=False, indent=2),
        }
    except Exception as e:
        print(f"[WARN] Risk events generation failed: {e}")
        fallback_events = [
            {
                "event_id": "E1",
                "event_name": "중동/수에즈/희망봉 우회 리스크",
                "severity": "HIGH",
                "summary": "중동 지정학 리스크와 우회 가능성으로 유럽향 해상 리드타임 증가 및 비용 상승 우려",
                "impact_modes": ["SEA"],
                "impact_regions": ["Middle East", "Suez", "Europe"],
                "impact_keywords": ["Hormuz", "Suez", "Cape of Good Hope", "rerouting"],
                "relevant_sites": ["HUNGARY_KOMAROM", "HUNGARY_IVANCSA"],
                "selection_hint": "헝가리 inbound 해상 HBL 우선 점검",
                "why_it_matters": "동아시아발 유럽향 자재/완제품 운송에 영향 가능성이 큼",
            },
            {
                "event_id": "E2",
                "event_name": "중동 항공 허브 차질 및 스페이스 부족",
                "severity": "HIGH",
                "summary": "중동 공역 및 허브 운영 차질로 항공 화물 backlog와 capacity reduction 우려",
                "impact_modes": ["AIR"],
                "impact_regions": ["Middle East", "Europe", "Asia"],
                "impact_keywords": ["air hub", "offloading", "capacity reduction", "backlog"],
                "relevant_sites": ["HUNGARY_KOMAROM", "HUNGARY_IVANCSA", "USA_GEORGIA"],
                "selection_hint": "긴급 자재 및 ETA 임박 항공건 우선 점검",
                "why_it_matters": "긴급 조달과 단납기 출하의 스페이스 확보에 영향 가능성이 있음",
            },
            {
                "event_id": "E3",
                "event_name": "booking stop 및 surcharge 확대 리스크",
                "severity": "MEDIUM",
                "summary": "선사 booking 제한 및 surcharge 확대 가능성으로 비용과 일정 불확실성 증가",
                "impact_modes": ["SEA"],
                "impact_regions": ["Middle East", "Europe"],
                "impact_keywords": ["booking stop", "surcharge", "service disruption"],
                "relevant_sites": ["HUNGARY_KOMAROM", "HUNGARY_IVANCSA", "KOREA_SEOSAN"],
                "selection_hint": "선사 공지와 납기 임박 해상건 우선 점검",
                "why_it_matters": "실제 선적 booking과 비용 조건에 직접 영향을 줄 수 있음",
            },
        ]
        return {
            "events": fallback_events,
            "raw_text": json.dumps(fallback_events, ensure_ascii=False, indent=2),
        }


def build_poc_risk_report_payload(
    target_date: str,
    llm_model: str = "gemini-flash",
    selected_event_name: str | None = None,
    selected_sites: list[str] | None = None,
) -> dict[str, str]:
    articles = load_latest_crawled_articles()
    shipping_rows = load_poc_shipping_candidates()
    selected_sites = selected_sites or []
    model_name = (llm_model or "gemini-flash").lower().strip()

    if not articles:
        return {
            "report_text": "뉴스 데이터가 없습니다.",
            "html": "<html><body><p>뉴스 데이터가 없습니다.</p></body></html>",
        }

    if not shipping_rows:
        return {
            "report_text": "선적 후보 CSV 데이터가 없습니다.",
            "html": "<html><body><p>선적 후보 CSV 데이터가 없습니다.</p></body></html>",
        }

    filtered_shipping_rows = filter_shipping_rows_by_sites(shipping_rows, selected_sites)

    try:
        report_text = generate_llm_summary(
            target_date=target_date,
            articles=articles,
            shipping_rows=filtered_shipping_rows,
            llm_model=model_name,
            selected_event_name=selected_event_name,
            selected_sites=selected_sites,
        )
    except Exception as e:
        print(f"[WARN] PoC risk report generation failed, fallback will be used: {e}")
        report_text = build_basic_summary(
            target_date=target_date,
            articles=articles,
            shipping_rows=filtered_shipping_rows,
            selected_event_name=selected_event_name,
            selected_sites=selected_sites,
        )

    html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #222; line-height: 1.7; padding: 24px;">
        <h1 style="font-size: 32px;">물류리스크 영향도 PoC 리포트</h1>
        <p><strong>기준일:</strong> {escape(target_date)}</p>
        <p><strong>모델:</strong> {escape(model_name)}</p>
        <p><strong>선택 이벤트:</strong> {escape(selected_event_name or '전체')}</p>
        <p><strong>선택 거점:</strong> {escape(', '.join(selected_sites) if selected_sites else '전체')}</p>
        <p><strong>분석 대상 선적건 수:</strong> {len(filtered_shipping_rows)}</p>
        <pre style="white-space: pre-wrap; font-family: Arial, sans-serif;">{escape(report_text)}</pre>
      </body>
    </html>
    """

    return {
        "report_text": report_text,
        "html": html,
    }