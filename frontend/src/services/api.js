const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

async function handleResponse(response) {
  if (!response.ok) {
    let detail = 'Request failed';
    try {
      const data = await response.json();
      detail = data.detail || data.message || detail;
    } catch {
      // ignore
    }
    throw new Error(detail);
  }
  return response.json();
}

export async function runCrawler(site) {
  const response = await fetch(`${API_BASE_URL}/api/crawler/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ site }),
  });
  return handleResponse(response);
}

export async function summarizeAndEmail(payload) {
  const response = await fetch(`${API_BASE_URL}/api/news/summarize-email`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return handleResponse(response);
}

export async function getCrawledJson(filePath) {
  const encodedPath = encodeURIComponent(filePath);
  const response = await fetch(`${API_BASE_URL}/api/crawler/json?file_path=${encodedPath}`);
  return handleResponse(response);
}

export async function generateRiskEvents(payload) {
  const response = await fetch(`${API_BASE_URL}/api/risk-events/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return handleResponse(response);
}

export async function generateRiskReport(payload) {
  const response = await fetch(`${API_BASE_URL}/api/risk-report/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return handleResponse(response);
}

export const exportCrawledNews = async (payload) => {
  const response = await fetch(`${API_BASE_URL}/api/export/crawled-news`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error('Failed to export crawled news');
  }
  return response.json();
};

export const exportRiskEvents = async (payload) => {
  const response = await fetch(`${API_BASE_URL}/api/export/risk-events`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error('Failed to export risk events');
  }
  return response.json();
};

export const exportJsonToGcs = async (payload) => {
  const response = await fetch(`${API_BASE_URL}/api/export/gcs`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || 'Failed to export JSON to GCS');
  }

  return response.json();
};

export const downloadCrawledNewsFile = (date) => {
  const params = new URLSearchParams();
  if (date) params.set('date', date);

  const url = `${API_BASE_URL}/api/export/crawled-news/download${
    params.toString() ? `?${params.toString()}` : ''
  }`;

  window.open(url, '_blank');
};

export const downloadRiskEventsFile = (date, llmModel = 'gemini-flash') => {
  const params = new URLSearchParams();
  if (date) params.set('date', date);
  if (llmModel) params.set('llm_model', llmModel);

  const url = `${API_BASE_URL}/api/export/risk-events/download?${params.toString()}`;
  window.open(url, '_blank');
};