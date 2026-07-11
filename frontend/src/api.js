const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function getJSON(path) {
  const res = await fetch(BASE + path);
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return res.json();
}

export const API_BASE = BASE;

async function postJSON(path) {
  const res = await fetch(BASE + path, { method: "POST" });
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return res.json();
}

export const api = {
  companies: () => getJSON("/companies"),
  topics: (ticker) => getJSON(`/companies/${ticker}/topics`),
  claims: (topic, ticker) =>
    getJSON(`/topics/${encodeURIComponent(topic)}/claims?ticker=${ticker}`),
  contradictions: (ticker, min = "low") =>
    getJSON(`/contradictions?ticker=${ticker}&min_severity=${min}`),
  citation: (id) => getJSON(`/claims/${id}/citation`),
  search: (q, ticker) =>
    getJSON(`/search?q=${encodeURIComponent(q)}${ticker ? `&ticker=${ticker}` : ""}`),
  // Company discovery + on-demand processing
  companySearch: (q) => getJSON(`/company-search?q=${encodeURIComponent(q)}`),
  popular: () => getJSON("/company-search/popular"),
  recent: () => getJSON("/company-search/recent"),
  process: (ticker) => postJSON(`/companies/${ticker}/process`),
  job: (id) => getJSON(`/jobs/${id}`),
};

export const SEV = { high: "var(--sev-high)", medium: "var(--sev-medium)", low: "var(--sev-low)" };
export const SEV_ORDER = { high: 3, medium: 2, low: 1 };

export function fmtDate(iso) {
  if (!iso) return "";
  const d = new Date(iso.length <= 10 ? iso + "T00:00:00" : iso);
  if (isNaN(d)) return iso;
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}
