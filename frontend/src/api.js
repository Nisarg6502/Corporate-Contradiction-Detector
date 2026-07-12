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

async function postJSONBody(path, body) {
  const res = await fetch(BASE + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return res.json();
}

// Server-Sent Events reader for the chat/summary endpoints. `handlers` maps
// SSE `event:` names (session, token, tool, citation, retry, error, done) to
// callbacks invoked with the parsed `data:` JSON payload. Fetch-based rather
// than EventSource because the chat endpoint is a POST with a JSON body.
async function streamSSE(path, options, handlers) {
  const res = await fetch(BASE + path, options);
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let sepIdx;
    while ((sepIdx = buffer.indexOf("\n\n")) !== -1) {
      const rawEvent = buffer.slice(0, sepIdx);
      buffer = buffer.slice(sepIdx + 2);
      let eventType = "message";
      const dataLines = [];
      for (const line of rawEvent.split("\n")) {
        if (line.startsWith("event:")) eventType = line.slice(6).trim();
        else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
      }
      let data = {};
      try {
        data = dataLines.length ? JSON.parse(dataLines.join("\n")) : {};
      } catch {
        // malformed frame — skip rather than throw and kill the stream
        continue;
      }
      handlers[eventType]?.(data);
    }
  }
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
  // Chatbot
  chatStream: (ticker, sessionId, message, handlers) =>
    streamSSE(
      `/companies/${ticker}/chat`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId ?? null, message }),
      },
      handlers
    ),
  chatSuggestions: (ticker) => getJSON(`/companies/${ticker}/chat/suggestions`),
  chatFollowups: (ticker, question, answer) =>
    postJSONBody(`/companies/${ticker}/chat/followups`, { question, answer }),
  systemInfo: () => getJSON("/system/info"),
  summaryStream: (ticker, handlers) =>
    streamSSE(`/companies/${ticker}/summary`, { method: "GET" }, handlers),
};

export const SEV = { high: "var(--sev-high)", medium: "var(--sev-medium)", low: "var(--sev-low)" };
export const SEV_ORDER = { high: 3, medium: 2, low: 1 };

export function fmtDate(iso) {
  if (!iso) return "";
  const d = new Date(iso.length <= 10 ? iso + "T00:00:00" : iso);
  if (isNaN(d)) return iso;
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}
