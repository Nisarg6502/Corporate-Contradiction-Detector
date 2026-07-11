import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";

function CompanyRow({ c, onOpen }) {
  return (
    <div onClick={() => onOpen(c)} style={{
      display: "flex", alignItems: "center", justifyContent: "space-between",
      gap: 12, padding: "12px 16px", background: "var(--paperCard)",
      border: "1px solid var(--hairline)", borderRadius: 10, cursor: "pointer",
      transition: "border-color 120ms ease",
    }}
      onMouseEnter={(e) => (e.currentTarget.style.borderColor = "var(--ink)")}
      onMouseLeave={(e) => (e.currentTarget.style.borderColor = "var(--hairline)")}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 10, minWidth: 0 }}>
        <span style={{ fontFamily: "var(--font-mono)", fontWeight: 600, fontSize: 13,
          color: "var(--ink)", flexShrink: 0 }}>{c.ticker}</span>
        <span style={{ fontSize: 13, color: "var(--inkSoft)", whiteSpace: "nowrap",
          overflow: "hidden", textOverflow: "ellipsis" }}>{c.name}</span>
      </div>
      {c.processed ? (
        <span style={{ display: "flex", alignItems: "center", gap: 6,
          fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--accent)", flexShrink: 0 }}>
          <span style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--accent)" }} />
          Ready</span>
      ) : (
        <span style={{ fontFamily: "var(--font-mono)", fontSize: 11,
          color: "var(--inkFaint)", flexShrink: 0 }}>Process →</span>
      )}
    </div>
  );
}

export default function Landing({ onOpen }) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState(null);
  const [popular, setPopular] = useState([]);
  const [recent, setRecent] = useState([]);
  const [down, setDown] = useState(false);
  const timer = useRef(null);

  useEffect(() => {
    api.popular().then(setPopular).catch(() => setDown(true));
    api.recent().then(setRecent).catch(() => {});
  }, []);

  useEffect(() => {
    clearTimeout(timer.current);
    if (!q.trim()) { setResults(null); return; }
    timer.current = setTimeout(() => {
      api.companySearch(q.trim()).then(setResults).catch(() => setResults([]));
    }, 250);
    return () => clearTimeout(timer.current);
  }, [q]);

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center",
      minHeight: "calc(100vh - 68px)", padding: "56px 24px 80px", textAlign: "center" }}>
      <div style={{ fontFamily: "var(--font-mono)", fontSize: 12, letterSpacing: "0.14em",
        textTransform: "uppercase", color: "var(--accent)", marginBottom: 18,
        animation: "fadeUp 700ms ease both" }}>Claim intelligence for public companies</div>
      <h1 style={{ fontFamily: "var(--font-serif)", fontWeight: 600, fontSize: 52, lineHeight: 1.08,
        maxWidth: 760, margin: "0 0 18px", color: "var(--ink)",
        animation: "fadeUp 700ms ease 80ms both" }}>Every claim, traced.<br />Every contradiction, found.</h1>
      <p style={{ fontSize: 16, color: "var(--inkSoft)", maxWidth: 560, lineHeight: 1.6,
        margin: "0 0 36px", animation: "fadeUp 700ms ease 160ms both" }}>
        Search any public company. We read its SEC filings, extract every claim, and flag
        where the story stopped adding up.</p>

      <div style={{ width: 480, maxWidth: "90vw", animation: "fadeUp 700ms ease 240ms both" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, background: "var(--paperCard)",
          border: "1px solid var(--hairline)", borderRadius: 12, padding: "12px 16px",
          boxShadow: "0 1px 2px rgba(0,0,0,.04)" }}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--inkSoft)" strokeWidth="2">
            <circle cx="11" cy="11" r="7" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          <input autoFocus value={q} onChange={(e) => setQ(e.target.value)}
            placeholder="Search a company by name or ticker (e.g. Apple, TSLA)…"
            style={{ border: "none", outline: "none", flex: 1, fontSize: 15, color: "var(--ink)",
              background: "transparent", fontFamily: "var(--font-sans)" }} />
        </div>

        {down && (
          <div style={{ marginTop: 16, padding: "12px 14px", borderRadius: 10,
            border: "1px solid var(--sev-high)", color: "var(--sev-high)", fontSize: 13,
            textAlign: "center" }}>
            Can't reach the backend. Start it with{" "}
            <code style={{ fontFamily: "var(--font-mono)" }}>uvicorn api.app:app --port 8000</code>.
          </div>
        )}

        <div style={{ marginTop: 18, textAlign: "left", display: "flex", flexDirection: "column", gap: 8 }}>
          {results !== null ? (
            results.length === 0
              ? <div style={{ fontSize: 13, color: "var(--inkFaint)", textAlign: "center", padding: 12 }}>No matches.</div>
              : results.map((c) => <CompanyRow key={c.ticker} c={c} onOpen={onOpen} />)
          ) : (
            <>
              <Section label="Popular">
                {popular.map((c) => <CompanyRow key={c.ticker} c={c} onOpen={onOpen} />)}
              </Section>
              {recent.length > 0 && (
                <Section label="Recently filed">
                  {recent.slice(0, 8).map((c) => <CompanyRow key={c.ticker} c={c} onOpen={onOpen} />)}
                </Section>
              )}
            </>
          )}
        </div>
      </div>

      <div style={{ marginTop: 48, fontSize: 12, color: "var(--inkFaint)", maxWidth: 540,
        animation: "fadeUp 700ms ease 320ms both" }}>
        NVDA is pre-loaded (with synthetic earnings-call excerpts containing planted
        contradictions). Any other company is processed live from its real SEC filings.
      </div>
    </div>
  );
}

function Section({ label, children }) {
  return (
    <div style={{ marginTop: 8 }}>
      <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, letterSpacing: ".1em",
        textTransform: "uppercase", color: "var(--inkFaint)", margin: "6px 4px 8px" }}>{label}</div>
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>{children}</div>
    </div>
  );
}
