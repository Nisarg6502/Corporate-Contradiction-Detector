import { useEffect, useState } from "react";
import { api } from "../api.js";
import { extractCitationOrder } from "../lib/citations.jsx";
import { renderMarkdown } from "../lib/markdown.jsx";

function CitationChips({ claimIds, onOpenCitation }) {
  if (!claimIds || claimIds.length === 0) return null;
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 20 }}>
      {claimIds.map((id, i) => (
        <button
          key={id}
          className="cp-press"
          onClick={() => onOpenCitation(id)}
          style={{
            border: "1px solid var(--hairline)", borderRadius: 999, background: "var(--accentSoft)",
            color: "var(--accent)", fontFamily: "var(--font-mono)", fontSize: 10,
            padding: "3px 10px", cursor: "pointer",
            animation: `popIn 300ms var(--ease-out) ${i * 45}ms both`,
          }}
          title={id}
        >
          Source {i + 1}
        </button>
      ))}
    </div>
  );
}

// Shimmering placeholder shown while the first summary tokens are still in
// flight — reads as "the document is being drafted" rather than a dead pause.
function SummarySkeleton() {
  const widths = ["96%", "88%", "92%", "70%", "0", "94%", "85%", "90%", "60%"];
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12, animation: "fadeIn 300ms ease both" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
        <span className="cp-typing"><span /><span /><span /></span>
        <span style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--inkFaint)" }}>
          Reading the filings
        </span>
      </div>
      {widths.map((w, i) => w === "0"
        ? <div key={i} style={{ height: 6 }} />
        : <div key={i} className="cp-skeleton" style={{ height: 12, width: w }} />)}
    </div>
  );
}

export default function SummaryPanel({ open, onClose, company, onOpenCitation }) {
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [attempt, setAttempt] = useState(0);
  const ticker = company?.ticker;
  const order = extractCitationOrder(text);

  useEffect(() => {
    if (!open || !ticker) return;
    let cancelled = false;
    setText("");
    setError(null);
    setLoading(true);
    api.summaryStream(ticker, {
      token: (d) => { if (!cancelled) setText((t) => t + d.text); },
      citation: () => {},
      error: (d) => { if (!cancelled) setError(d.message); },
      done: () => { if (!cancelled) setLoading(false); },
    }).catch((e) => { if (!cancelled) { setError(e.message || "Failed to load summary."); setLoading(false); } });
    return () => { cancelled = true; };
  }, [open, ticker, attempt]);

  if (!open) return null;

  return (
    <div onClick={onClose} style={{
      position: "fixed", inset: 0, background: "rgba(20,18,14,0.35)", zIndex: 58,
      display: "flex", justifyContent: "center", alignItems: "flex-start",
      animation: "fadeIn 220ms ease both", overflowY: "auto", padding: "48px 20px",
    }}>
      <div onClick={(e) => e.stopPropagation()} style={{
        width: 640, maxWidth: "94vw", background: "var(--paperCard)", borderRadius: 12,
        boxShadow: "0 24px 60px rgba(0,0,0,.2)", padding: "32px 36px 40px",
        animation: "scaleIn 260ms cubic-bezier(.2,.8,.2,1) both",
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 20 }}>
          <div>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, textTransform: "uppercase",
              letterSpacing: ".08em", color: "var(--inkFaint)" }}>Executive summary</div>
            <div style={{ fontFamily: "var(--font-serif)", fontSize: 20, color: "var(--ink)", marginTop: 4 }}>
              {company?.name || ticker}
            </div>
          </div>
          <button onClick={onClose} style={{ border: "none", background: "transparent", fontSize: 22,
            cursor: "pointer", color: "var(--inkSoft)", lineHeight: 1 }}>×</button>
        </div>

        {error ? (
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ color: "var(--sev-high)", fontFamily: "var(--font-mono)", fontSize: 12 }}>
              {error}
            </span>
            <button onClick={() => setAttempt((a) => a + 1)} title="Retry" style={{
              border: "1px solid var(--hairline)", borderRadius: 999, background: "transparent",
              color: "var(--inkSoft)", fontSize: 13, width: 22, height: 22, lineHeight: 1,
              cursor: "pointer", padding: 0, flexShrink: 0,
            }}>
              ↻
            </button>
          </div>
        ) : !text && loading ? (
          <SummarySkeleton />
        ) : (
          <div style={{ fontFamily: "var(--font-serif)", fontSize: 15.5, lineHeight: 1.75, color: "var(--ink)",
            display: "flex", flexDirection: "column", gap: 2, animation: "fadeIn 300ms ease both" }}>
            {renderMarkdown(text, order, onOpenCitation)}
            {loading && <span className="cp-caret" />}
          </div>
        )}

        <CitationChips claimIds={order} onOpenCitation={onOpenCitation} />
      </div>
    </div>
  );
}
