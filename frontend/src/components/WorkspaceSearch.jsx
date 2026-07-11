import { useState } from "react";
import { api, SEV } from "../api.js";

export default function WorkspaceSearch({ ticker, onResult }) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState(null);
  const [busy, setBusy] = useState(false);

  async function run(e) {
    e.preventDefault();
    if (!q.trim()) { setResults(null); return; }
    setBusy(true);
    try {
      const r = await api.search(q.trim(), ticker);
      setResults(r.results || []);
    } finally { setBusy(false); }
  }

  return (
    <div style={{ position: "relative", width: 210 }}>
      <form onSubmit={run} style={{ display: "flex", alignItems: "center", gap: 8,
        background: "var(--paperCard)", border: "1px solid var(--hairline)",
        borderRadius: 999, padding: "7px 14px" }}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--inkSoft)" strokeWidth="2">
          <circle cx="11" cy="11" r="7" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
        </svg>
        <input value={q} onChange={(e) => setQ(e.target.value)}
          placeholder="Search claims…"
          style={{ border: "none", outline: "none", flex: 1, fontSize: 13,
            background: "transparent", color: "var(--ink)", fontFamily: "var(--font-sans)" }} />
        {q && <span onClick={() => { setQ(""); setResults(null); }}
          style={{ cursor: "pointer", color: "var(--inkFaint)", fontSize: 14 }}>×</span>}
      </form>

      {results !== null && (
        <div style={{ position: "absolute", top: "calc(100% + 6px)", right: 0, width: 420,
          maxWidth: "70vw", background: "var(--paperCard)", border: "1px solid var(--hairline)",
          borderRadius: 12, boxShadow: "0 12px 32px rgba(0,0,0,.12)", zIndex: 30,
          maxHeight: 360, overflowY: "auto", padding: 6 }}>
          {busy && <div style={{ padding: 12, fontSize: 12, color: "var(--inkFaint)" }}>Searching…</div>}
          {!busy && results.length === 0 && (
            <div style={{ padding: 12, fontSize: 12, color: "var(--inkFaint)" }}>No matches.</div>
          )}
          {results.map((r) => (
            <div key={r.claim_id} onClick={() => { onResult(r); setResults(null); }}
              style={{ padding: "10px 12px", borderRadius: 8, cursor: "pointer" }}
              onMouseEnter={(e) => (e.currentTarget.style.background = "var(--accentSoft)")}
              onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 8, marginBottom: 4 }}>
                <span style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--inkFaint)" }}>
                  {r.topic} · {r.source_type}</span>
                {r.contradictions?.length > 0 && (
                  <span style={{ fontFamily: "var(--font-mono)", fontSize: 10,
                    color: SEV[r.contradictions[0].severity] }}>⚠ {r.contradictions[0].severity}</span>
                )}
              </div>
              <div style={{ fontFamily: "var(--font-serif)", fontSize: 13, color: "var(--ink)", lineHeight: 1.4 }}>
                “{r.quote_span.slice(0, 110)}{r.quote_span.length > 110 ? "…" : ""}”</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
