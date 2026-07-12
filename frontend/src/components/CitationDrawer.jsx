import { fmtDate } from "../api.js";

// The highlight sweeps in left-to-right so the verified quote-span "reveals"
// itself rather than just appearing — the moment the app earns its credibility.
const markStyle = {
  background: "linear-gradient(color-mix(in oklch, var(--accent) 35%, var(--paperCard)),"
    + " color-mix(in oklch, var(--accent) 35%, var(--paperCard)))",
  backgroundRepeat: "no-repeat",
  backgroundSize: "0% 100%",
  padding: "1px 2px", borderRadius: 2,
  animation: "markSweep 720ms var(--ease-out) 340ms both",
};

function splitQuote(text, quote) {
  const idx = text ? text.indexOf(quote) : -1;
  if (idx < 0) return { before: text || "", mark: quote || "", after: "" };
  return { before: text.slice(0, idx), mark: quote, after: text.slice(idx + quote.length) };
}

export default function CitationDrawer({ citation, loading, onClose }) {
  const stop = (e) => e.stopPropagation();
  const r = citation?.render;
  const isSynthetic = r?.type === "pdf";
  const { before, mark, after } = r ? splitQuote(r.paragraph_text, r.quote_span) : {};

  return (
    <div onClick={onClose} style={{
      position: "fixed", inset: 0, background: "rgba(20,18,14,0.35)", zIndex: 60,
      display: "flex", justifyContent: "flex-end", animation: "fadeIn 250ms ease both",
    }}>
      <div className="drawer" onClick={stop} style={{
        width: 520, maxWidth: "92vw", height: "100%", background: "var(--paperCard)",
        boxShadow: "-12px 0 40px rgba(0,0,0,.15)", padding: "36px 36px 40px",
        overflowY: "auto", animation: "slideInRight 380ms cubic-bezier(.2,.8,.2,1) both",
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
          <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, textTransform: "uppercase",
            letterSpacing: ".08em", color: "var(--inkFaint)" }}>Source citation</span>
          <button onClick={onClose} style={{ border: "none", background: "transparent", fontSize: 22,
            cursor: "pointer", color: "var(--inkSoft)", lineHeight: 1 }}>×</button>
        </div>

        {loading || !citation ? (
          <div style={{ color: "var(--inkFaint)", fontSize: 14 }}>Loading citation…</div>
        ) : (
          <>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--inkSoft)", marginBottom: 6 }}>
              {citation.document.doc_type} · {citation.document.period || fmtDate(citation.document.date)}
            </div>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--inkFaint)", marginBottom: 20 }}>
              {r.section_heading || citation.anchor.section_id}
            </div>

            {isSynthetic ? (
              <div style={{ border: "1px solid var(--hairline)", borderRadius: 4,
                background: "repeating-linear-gradient(var(--paperCard),var(--paperCard) 27px,var(--hairline) 28px)",
                padding: "28px 24px", boxShadow: "0 1px 3px rgba(0,0,0,.06)" }}>
                <div style={{ fontFamily: "var(--font-serif)", fontSize: 15, lineHeight: 1.9, color: "var(--ink)" }}>
                  {before}<mark style={markStyle}>{mark}</mark>{after}
                </div>
                <div style={{ marginTop: 18, fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--inkFaint)" }}>
                  Rendered from PDF · page {r.page}
                </div>
              </div>
            ) : (
              <div style={{ borderLeft: "3px solid var(--hairline)", paddingLeft: 20 }}>
                <div style={{ fontFamily: "var(--font-serif)", fontWeight: 600, fontSize: 14,
                  marginBottom: 10, color: "var(--inkSoft)" }}>{r.section_heading}</div>
                <div style={{ fontFamily: "var(--font-serif)", fontSize: 16, lineHeight: 1.85,
                  textAlign: "justify", color: "var(--ink)" }}>
                  {before}<mark style={markStyle}>{mark}</mark>{after}
                </div>
              </div>
            )}

            <div style={{ marginTop: 28, display: "flex", alignItems: "center", gap: 8,
              fontFamily: "var(--font-mono)", fontSize: 11, color: "#3f7d54",
              animation: "slideUpIn 500ms var(--ease-out) 1000ms both" }}>
              <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#3f7d54",
                animation: "popIn 400ms var(--ease-out) 1000ms both" }} />
              Quote-span verified exact match
            </div>
            <div style={{ marginTop: 20, paddingTop: 20, borderTop: "1px solid var(--hairline)",
              fontSize: 13, color: "var(--inkSoft)" }}>
              {citation.claim.speaker}{citation.claim.role ? ` · ${citation.claim.role}` : ""}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
