import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";

const STEPS = [
  { key: "fetching", label: "Fetching SEC filings",
    plain: "Downloading the company's latest annual and quarterly reports straight from the SEC." },
  { key: "extracting", label: "Extracting claims",
    plain: "Reading every page and noting the specific things management claimed — in their exact words." },
  { key: "graph", label: "Building the knowledge graph",
    plain: "Connecting those claims into a map of who said what, about what, and when." },
  { key: "indexing", label: "Indexing for semantic search",
    plain: "Making every claim searchable by meaning, not just keywords." },
  { key: "detecting", label: "Detecting contradictions",
    plain: "Comparing claims across time and asking an AI whether any of them contradict each other." },
];
const ORDER = STEPS.map((s) => s.key);

function mmss(s) {
  const m = Math.floor(s / 60), r = s % 60;
  return `${m}:${String(r).padStart(2, "0")}`;
}

export default function Processing({ company, onDone, onBack }) {
  const [job, setJob] = useState(null);
  const [error, setError] = useState(null);
  const [elapsed, setElapsed] = useState(0);
  const [showDetails, setShowDetails] = useState(false);
  const poll = useRef(null);
  const started = useRef(false);

  useEffect(() => {
    const t = setInterval(() => setElapsed((e) => e + 1), 1000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    (async () => {
      try {
        const res = await api.process(company.ticker);
        if (res.status === "done" || res.already_processed) { onDone(company); return; }
        const id = res.job_id;
        poll.current = setInterval(async () => {
          try {
            const j = await api.job(id);
            setJob(j);
            if (j.status === "done") { clearInterval(poll.current); setTimeout(() => onDone(company), 500); }
            if (j.status === "error") { clearInterval(poll.current); setError(j.message || "Processing failed."); }
          } catch (e) { /* transient */ }
        }, 1200);
      } catch (e) { setError(String(e)); }
    })();
    return () => clearInterval(poll.current);
  }, [company]);

  const stage = job?.stage || "queued";
  const pct = job?.progress || 0;
  const curIdx = ORDER.indexOf(stage);
  const stepNum = stage === "done" ? STEPS.length : Math.max(curIdx + 1, 1);

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center",
      justifyContent: "center", minHeight: "calc(100vh - 68px)", padding: "40px 24px" }}>
      <div style={{ width: 540, maxWidth: "92vw", animation: "fadeUp 500ms ease both" }}>
        <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, letterSpacing: ".12em",
          textTransform: "uppercase", color: "var(--accent)", marginBottom: 10 }}>
          Processing · live from SEC EDGAR</div>
        <h1 style={{ fontFamily: "var(--font-serif)", fontSize: 30, margin: "0 0 6px", color: "var(--ink)" }}>
          {company.name}</h1>
        <div style={{ fontFamily: "var(--font-mono)", fontSize: 13, color: "var(--inkSoft)", marginBottom: 26 }}>
          {company.ticker}</div>

        {error ? (
          <div>
            <div style={{ padding: 16, border: "1px solid var(--sev-high)", borderRadius: 12,
              color: "var(--sev-high)", fontSize: 14, marginBottom: 16 }}>{error}</div>
            <button onClick={onBack} style={btn}>← Back to search</button>
          </div>
        ) : (
          <>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline",
              marginBottom: 8, fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--inkSoft)" }}>
              <span>Step {stepNum} of {STEPS.length}</span>
              <span style={{ color: "var(--ink)", fontWeight: 500 }}>{pct}%</span>
            </div>
            <div style={{ height: 6, background: "var(--hairline)", borderRadius: 999, overflow: "hidden", marginBottom: 22 }}>
              <div style={{ height: "100%", width: `${pct}%`, background: "var(--accent)",
                borderRadius: 999, transition: "width 500ms ease" }} />
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              {STEPS.map((s, i) => {
                const done = curIdx > i || stage === "done";
                const active = curIdx === i && stage !== "done";
                return (
                  <div key={s.key} style={{ display: "flex", alignItems: "center", gap: 12,
                    opacity: done || active ? 1 : 0.45 }}>
                    <span style={{ width: 18, height: 18, borderRadius: "50%", flexShrink: 0,
                      display: "flex", alignItems: "center", justifyContent: "center",
                      background: done ? "var(--accent)" : "transparent",
                      border: done ? "none" : `2px solid ${active ? "var(--accent)" : "var(--hairline)"}` }}>
                      {done && <span style={{ color: "var(--paperCard)", fontSize: 11 }}>✓</span>}
                      {active && <span style={{ width: 6, height: 6, borderRadius: "50%",
                        background: "var(--accent)", animation: "nodeIn 700ms ease infinite alternate" }} />}
                    </span>
                    <span style={{ fontSize: 14, color: "var(--ink)", fontWeight: active ? 600 : 400 }}>{s.label}</span>
                  </div>
                );
              })}
            </div>

            <div style={{ marginTop: 22, fontSize: 13, color: "var(--inkSoft)", minHeight: 20 }}>
              {job?.message || "Starting…"}</div>
            <div style={{ marginTop: 8, display: "flex", justifyContent: "space-between",
              fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--inkFaint)" }}>
              <span>Usually ~3–5 minutes · about a coffee run ☕</span>
              <span>Elapsed {mmss(elapsed)}</span>
            </div>

            {/* Collapsible: what's happening behind the scenes */}
            <button onClick={() => setShowDetails((v) => !v)}
              style={{ marginTop: 20, padding: "8px 0", border: "none", background: "transparent",
                color: "var(--accent)", fontFamily: "var(--font-mono)", fontSize: 12, cursor: "pointer",
                display: "flex", alignItems: "center", gap: 6 }}>
              {showDetails ? "▾" : "▸"} Peek behind the scenes
            </button>
            {showDetails && (
              <div style={{ overflow: "hidden", animation: "expandDown 320ms ease both",
                borderLeft: "2px solid var(--hairline)", paddingLeft: 16, marginTop: 4,
                display: "flex", flexDirection: "column", gap: 12 }}>
                {STEPS.map((s, i) => {
                  const done = curIdx > i || stage === "done";
                  const active = curIdx === i && stage !== "done";
                  return (
                    <div key={s.key} style={{ opacity: done || active ? 1 : 0.5 }}>
                      <div style={{ fontFamily: "var(--font-mono)", fontSize: 11,
                        color: active ? "var(--accent)" : "var(--inkFaint)", marginBottom: 2 }}>
                        {done ? "done" : active ? "now" : "next"} · {s.label}</div>
                      <div style={{ fontSize: 13, color: "var(--inkSoft)", lineHeight: 1.5 }}>{s.plain}</div>
                    </div>
                  );
                })}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

const btn = {
  padding: "9px 16px", borderRadius: 999, border: "1px solid var(--ink)",
  background: "transparent", color: "var(--ink)", fontFamily: "var(--font-mono)",
  fontSize: 12, cursor: "pointer",
};
