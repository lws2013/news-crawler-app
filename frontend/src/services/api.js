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