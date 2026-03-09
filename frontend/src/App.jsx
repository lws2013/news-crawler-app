import { useMemo, useState } from 'react';
import SectionCard from './components/SectionCard';
import StatMessage from './components/StatMessage';
import {
  runCrawler,
  summarizeAndEmail,
  getCrawledJson,
  generateRiskEvents,
  generateRiskReport,
} from './services/api';

const SITE_OPTIONS = [
  { value: 'all', label: 'all' },
  { value: 'busanpa', label: 'BusanPA' },
  { value: 'cargonews', label: 'Cargo News' },
  { value: 'cello', label: 'Cello Square' },
  { value: 'flexport', label: 'Flexport' },
  { value: 'iata', label: 'IATA' },
  { value: 'kita', label: 'KITA' },
  { value: 'kotra', label: 'KOTRA' },
  { value: 'ksg', label: 'KSG' },
  { value: 'oceanpress', label: 'OceanPress' },
  { value: 'sea', label: 'SEA' },
  { value: 'shippingnews', label: 'Shipping News' },
  { value: 'surff', label: 'SURFF' },
  { value: 'ulogistics', label: 'uLogistics' },
];

const LLM_OPTIONS = [
  { value: 'gemini-flash', label: 'Gemini Flash' },
  { value: 'openai', label: 'OpenAI' },
];

const SITE_FILTER_OPTIONS = [
  { value: 'KOREA_SEOSAN', label: 'KOREA_SEOSAN' },
  { value: 'HUNGARY_KOMAROM', label: 'HUNGARY_KOMAROM' },
  { value: 'HUNGARY_IVANCSA', label: 'HUNGARY_IVANCSA' },
  { value: 'USA_GEORGIA', label: 'USA_GEORGIA' },
];

function formatToday() {
  const now = new Date();
  const yyyy = now.getFullYear();
  const mm = String(now.getMonth() + 1).padStart(2, '0');
  const dd = String(now.getDate()).padStart(2, '0');
  return `${yyyy}-${mm}-${dd}`;
}

export default function App() {
  const [site, setSite] = useState('all');
  const [llmModel, setLlmModel] = useState('gemini-flash');
  const [date, setDate] = useState(formatToday());
  const [email, setEmail] = useState('');
  const [crawlerLoading, setCrawlerLoading] = useState(false);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [jsonLoading, setJsonLoading] = useState(false);
  const [riskEventsLoading, setRiskEventsLoading] = useState(false);
  const [riskReportLoading, setRiskReportLoading] = useState(false);

  const [status, setStatus] = useState({ type: 'info', title: '', message: '' });
  const [articles, setArticles] = useState([]);
  const [savedFile, setSavedFile] = useState('');
  const [siteCounts, setSiteCounts] = useState({});
  const [jsonModalOpen, setJsonModalOpen] = useState(false);
  const [jsonModalData, setJsonModalData] = useState(null);

  const [riskEvents, setRiskEvents] = useState([]);
  const [selectedEvent, setSelectedEvent] = useState(null);
  const [selectedSites, setSelectedSites] = useState([]);
  const [riskReport, setRiskReport] = useState('');

  const summaryDisabled = useMemo(() => {
    return !date || !email || !llmModel || summaryLoading;
  }, [date, email, llmModel, summaryLoading]);

  function toggleSelectedSite(siteCode) {
    setSelectedSites((prev) =>
      prev.includes(siteCode) ? prev.filter((x) => x !== siteCode) : [...prev, siteCode]
    );
  }

  async function onRunCrawler() {
    setCrawlerLoading(true);
    setStatus({
      type: 'info',
      title: 'Crawler running',
      message: '뉴스 수집을 시작했습니다.',
    });

    try {
      const result = await runCrawler(site);
      setArticles(result.data || []);
      setSavedFile(result.saved_file || '');
      setSiteCounts(result.site_counts || {});
      setStatus({
        type: 'success',
        title: 'Crawler completed',
        message: `${result.message || '뉴스 수집이 완료되었습니다.'} (${result.collected_count ?? 0}건)`,
      });
    } catch (error) {
      setStatus({
        type: 'error',
        title: 'Error running crawler',
        message: error.message || 'Failed to fetch',
      });
    } finally {
      setCrawlerLoading(false);
    }
  }

  async function onSummarizeAndSend() {
    setSummaryLoading(true);
    setStatus({
      type: 'info',
      title: 'Summarizing news',
      message: `${llmModel} 모델로 요약 생성 및 이메일 발송을 진행합니다.`,
    });

    try {
      const result = await summarizeAndEmail({
        date,
        email,
        llm_model: llmModel,
      });

      setStatus({
        type: 'success',
        title: 'Summary email sent',
        message: result.message || '요약 메일 발송이 완료되었습니다.',
      });
    } catch (error) {
      setStatus({
        type: 'error',
        title: 'Error sending summary email',
        message: error.message || 'Failed to fetch',
      });
    } finally {
      setSummaryLoading(false);
    }
  }

  async function onViewJson() {
    if (!savedFile) return;

    setJsonLoading(true);
    try {
      const result = await getCrawledJson(savedFile);
      setJsonModalData(result.data || []);
      setJsonModalOpen(true);
    } catch (error) {
      setStatus({
        type: 'error',
        title: 'Error loading JSON',
        message: error.message || 'JSON 파일을 불러오지 못했습니다.',
      });
    } finally {
      setJsonLoading(false);
    }
  }

  async function onGenerateRiskEvents() {
    setRiskEventsLoading(true);
    setSelectedEvent(null);
    setRiskReport('');

    setStatus({
      type: 'info',
      title: 'Generating risk events',
      message: `${llmModel} 모델로 오늘의 주요 물류 이벤트를 분석합니다.`,
    });

    try {
      const result = await generateRiskEvents({
        date,
        llm_model: llmModel,
      });

      setRiskEvents(result.events || []);

      setStatus({
        type: 'success',
        title: 'Risk events generated',
        message: result.message || '오늘의 주요 물류 이벤트 분석이 완료되었습니다.',
      });
    } catch (error) {
      setRiskEvents([]);
      setStatus({
        type: 'error',
        title: 'Error generating risk events',
        message: error.message || '이벤트 생성 실패',
      });
    } finally {
      setRiskEventsLoading(false);
    }
  }

  async function onGenerateRiskReport() {
    setRiskReportLoading(true);

    const payload = {
      date,
      llm_model: llmModel,
      selected_event_id: selectedEvent?.event_id || null,
      selected_event_name: selectedEvent?.event_name || null,
      selected_sites: selectedSites,
    };

    console.log('risk report payload = ', payload);

    setStatus({
      type: 'info',
      title: 'Generating risk report',
      message: `${llmModel} 모델로 선택 이벤트 기준 PoC 물류리스크 영향도 리포트를 생성합니다.`,
    });

    try {
      const result = await generateRiskReport(payload);

      setRiskReport(result.report_text || '');

      setStatus({
        type: 'success',
        title: 'Risk report generated',
        message: result.message || '물류리스크 영향도 리포트 생성이 완료되었습니다.',
      });
    } catch (error) {
      setRiskReport('');
      setStatus({
        type: 'error',
        title: 'Error generating risk report',
        message: error.message || '리포트 생성 실패',
      });
    } finally {
      setRiskReportLoading(false);
    }
  }

  return (
    <main className="page">
      <div className="hero">
        <h1 className="hero-title">News Crawler Dashboard</h1>
        <p className="hero-subtitle">
          SK온 물류MI 뉴스 수집 및 리스크 PoC 페이지입니다.
          <br />
          오늘의 주요 물류 이벤트를 고르고 영향 선적건을 확인하세요.
        </p>
      </div>

      <SectionCard>
        <div className="row responsive-row">
          <select className="input select" value={site} onChange={(e) => setSite(e.target.value)}>
            {SITE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>

          <button className="primary-button crawler-button" onClick={onRunCrawler} disabled={crawlerLoading}>
            {crawlerLoading ? 'Running...' : 'Run Crawler'}
          </button>
        </div>
      </SectionCard>

      <SectionCard>
        <div className="section-header">뉴스 요약 및 이메일 발송</div>
        <p className="section-description">
          LLM 모델을 선택하고 날짜와 이메일을 입력한 뒤, 해당 날짜의 뉴스를 물류 관점으로 요약해 메일로 받을 수 있습니다.
        </p>

        <div className="row responsive-row form-row">
          <div className="field">
            <label className="label">LLM 모델</label>
            <select className="input select" value={llmModel} onChange={(e) => setLlmModel(e.target.value)}>
              {LLM_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          <div className="field">
            <label className="label">날짜</label>
            <input className="input" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
          </div>

          <div className="field">
            <label className="label">이메일</label>
            <input
              className="input"
              type="email"
              placeholder="your@email.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
        </div>

        <button className="secondary-button summary-button" onClick={onSummarizeAndSend} disabled={summaryDisabled}>
          {summaryLoading ? 'Sending...' : '요약 및 이메일 발송'}
        </button>
      </SectionCard>

      <SectionCard>
        <div className="section-header">오늘의 주요 물류 이벤트 분석</div>
        <p className="section-description">
          전체 물류 뉴스를 탐독하여 심각도와 당사 생산거점 관련성을 기준으로 주요 이벤트를 추출합니다.
        </p>

        <button className="secondary-button summary-button" onClick={onGenerateRiskEvents} disabled={riskEventsLoading}>
          {riskEventsLoading ? 'Generating...' : '오늘의 물류 이벤트 분석'}
        </button>
      </SectionCard>

      {riskEvents.length > 0 && (
        <SectionCard>
          <div className="section-header">이벤트 선택</div>
          <p className="section-description">
            관심 있는 리스크 이벤트를 하나 선택하고, 영향 분석할 생산거점을 체크하세요.
          </p>

          <div className="event-list">
            {riskEvents.map((event) => {
              const isSelected = selectedEvent?.event_id === event.event_id;

              return (
                <label
                  key={event.event_id}
                  className={`event-card ${isSelected ? 'selected' : ''}`}
                >
                  <div className="event-card-select">
                    <input
                      type="radio"
                      name="risk-event"
                      checked={isSelected}
                      onChange={() => setSelectedEvent(event)}
                    />
                    <span className="event-card-select-text">이 이벤트 선택</span>
                  </div>

                  <div className="event-card-top">
                    <strong>{event.event_name}</strong>
                    <span className={`severity-badge severity-${(event.severity || '').toLowerCase()}`}>
                      {event.severity}
                    </span>
                  </div>

                  <div className="event-summary">{event.summary}</div>

                  <div className="event-meta">
                    <div><strong>영향 모드:</strong> {(event.impact_modes || []).join(', ')}</div>
                    <div><strong>관련 거점:</strong> {(event.relevant_sites || []).join(', ')}</div>
                    <div><strong>선택 힌트:</strong> {event.selection_hint}</div>
                    <div><strong>중요 이유:</strong> {event.why_it_matters}</div>
                  </div>
                </label>
              );
            })}
          </div>

          {selectedEvent && (
            <div style={{ marginTop: 20 }}>
              <div className="section-header" style={{ fontSize: 18 }}>현재 선택된 리스크 이벤트</div>
              <div className="section-description">
                <strong>{selectedEvent.event_name}</strong> / 심각도: {selectedEvent.severity}
                <br />
                관련 거점: {(selectedEvent.relevant_sites || []).join(', ')}
              </div>
            </div>
          )}

          <div className="site-selector">
            <div className="label" style={{ marginBottom: 12 }}>생산거점 선택</div>
            <div className="site-check-grid">
              {SITE_FILTER_OPTIONS.map((siteOption) => (
                <label key={siteOption.value} className="site-check-item">
                  <input
                    type="checkbox"
                    checked={selectedSites.includes(siteOption.value)}
                    onChange={() => toggleSelectedSite(siteOption.value)}
                  />
                  <span>{siteOption.label}</span>
                </label>
              ))}
            </div>
          </div>

          <button
            className="secondary-button summary-button"
            onClick={onGenerateRiskReport}
            disabled={riskReportLoading || !selectedEvent || selectedSites.length === 0}
          >
            {riskReportLoading ? 'Generating...' : '선택 이벤트 기준 영향 선적 리포트 생성'}
          </button>
        </SectionCard>
      )}

      <StatMessage type={status.type} title={status.title} message={status.message} />

      {riskReport && (
        <SectionCard>
          <div className="section-header">PoC 리스크 리포트 결과</div>
          <pre className="json-pretty">{riskReport}</pre>
        </SectionCard>
      )}

      {articles.length > 0 && (
        <SectionCard className="articles-section">
          <div className="articles-header">
            <div className="articles-title-wrap">
              <h2 className="articles-title">Extracted Articles</h2>
              <span className="articles-badge">{articles.length} items</span>
            </div>

            {savedFile ? (
              <button className="json-button" onClick={onViewJson} disabled={jsonLoading}>
                {jsonLoading ? 'Loading...' : 'View JSON'}
              </button>
            ) : null}
          </div>

          {Object.keys(siteCounts).length > 0 && (
            <div className="site-counts-wrap">
              {Object.entries(siteCounts).map(([siteName, count]) => (
                <div key={siteName} className="site-count-chip">
                  <span className="site-count-name">{siteName}</span>
                  <span className="site-count-value">{count}</span>
                </div>
              ))}
            </div>
          )}

          <div className="article-grid">
            {articles.map((article, index) => (
              <a
                key={`${article.url}-${index}`}
                href={article.url}
                target="_blank"
                rel="noreferrer"
                className="article-card"
              >
                <div className="article-image-wrap">
                  {article.images && article.images.length > 0 ? (
                    <img src={article.images[0]} alt={article.title || 'article'} className="article-image" />
                  ) : (
                    <div className="article-image placeholder">No Image</div>
                  )}
                </div>

                <div className="article-body">
                  <div className="article-meta-row">
                    <span className="article-source-badge">{article.source || 'unknown'}</span>
                    <span className="article-date">{article.date || '날짜 없음'}</span>
                  </div>

                  <div className="article-card-title">{article.title || '제목 없음'}</div>

                  <div className="article-summary">
                    {article.content
                      ? article.content.slice(0, 120) + (article.content.length > 120 ? '...' : '')
                      : '본문 없음'}
                  </div>
                </div>
              </a>
            ))}
          </div>
        </SectionCard>
      )}

      {jsonModalOpen && (
        <div className="modal-overlay" onClick={() => setJsonModalOpen(false)}>
          <div className="modal-box" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">Crawled JSON Data</h3>
              <button className="modal-close" onClick={() => setJsonModalOpen(false)}>
                ✕
              </button>
            </div>

            <div className="modal-content">
              <pre className="json-pretty">{JSON.stringify(jsonModalData, null, 2)}</pre>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}