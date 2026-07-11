import { useEffect, useState } from "react";
import { api } from "../api.js";

const STAGES = [
  { title: "Ingest", plain: "We grab the company's own words straight from the source — its SEC filings (and, for the NVDA demo, synthetic earnings-call excerpts).",
    body: "10-K / 10-Q / 8-K are pulled from EDGAR; synthetic transcripts are rendered to PDF.", tech: ["edgartools", "PyMuPDF"] },
  { title: "Parse", plain: "We break those long documents into bite-sized pieces, remembering exactly where each one came from.",
    body: "HTML (BeautifulSoup) and PDFs (PyMuPDF) become paragraph-level chunks, each with a stable position anchor.", tech: ["BeautifulSoup", "anchors"] },
  { title: "Extract", plain: "An AI reads every piece and writes down each claim management made — copying their exact wording.",
    body: "Claims are pulled per curated topic. A hard guardrail rejects any claim whose quote-span isn't a verbatim substring of the source.", tech: ["gpt-oss (Ollama)", "quote-span guardrail"], llm: true },
  { title: "Store", plain: "Every claim becomes a node in a graph and a point in a search index.",
    body: "Claims, speakers, documents and topics form a Neo4j knowledge graph; embeddings go to Qdrant for semantic search.", tech: ["Neo4j", "Qdrant", "FastEmbed"] },
  { title: "Detect", plain: "We line up claims about the same topic across time and ask an AI: do any of these contradict each other?",
    body: "Graph traversal finds candidate pairs; an LLM judges each for whether it's a real contradiction, with severity + reasoning.", tech: ["Cypher", "LLM judgment"], llm: true },
  { title: "Serve", plain: "You get a timeline, a graph, hybrid search, and a citation for every single claim.",
    body: "A FastAPI backend and this React app surface it all, with book-page citations that trace each claim to its source.", tech: ["FastAPI", "React"] },
];

const W = 1000, Y = 78, H = 56, w = 132;
const gap = (W - 6 * w) / 5;
const xs = STAGES.map((_, i) => i * (w + gap));
const cy = Y + H / 2;

export default function HowItWorks({ onBack }) {
  const [stats, setStats] = useState(null);
  const [active, setActive] = useState(0);
  const [hovered, setHovered] = useState(-1);

  useEffect(() => {
    api.companies().then((cs) => setStats({
      companies: cs.length,
      claims: cs.reduce((s, c) => s + (c.claims || 0), 0),
    })).catch(() => {});
  }, []);

  const s = STAGES[active];
  const next = () => setActive((a) => Math.min(a + 1, STAGES.length - 1));
  const prev = () => setActive((a) => Math.max(a - 1, 0));

  return (
    <div style={{ maxWidth: 1040, margin: "0 auto", padding: "40px 32px 80px",
      animation: "fadeIn 400ms ease both" }}>
      <button onClick={onBack} style={{ padding: "6px 12px", borderRadius: 999,
        border: "1px solid var(--hairline)", background: "transparent", color: "var(--inkSoft)",
        fontFamily: "var(--font-mono)", fontSize: 12, cursor: "pointer", marginBottom: 20 }}>← Back</button>

      <div style={{ fontFamily: "var(--font-mono)", fontSize: 12, letterSpacing: ".12em",
        textTransform: "uppercase", color: "var(--accent)", marginBottom: 12,
        animation: "fadeUp 600ms ease both" }}>How it works</div>
      <h1 style={{ fontFamily: "var(--font-serif)", fontSize: 40, lineHeight: 1.1, margin: "0 0 14px",
        color: "var(--ink)", maxWidth: 720, animation: "fadeUp 600ms ease 80ms both" }}>
        From raw filings to traceable contradictions.</h1>
      <p style={{ fontSize: 16, color: "var(--inkSoft)", maxWidth: 620, lineHeight: 1.6, margin: "0 0 8px",
        animation: "fadeUp 600ms ease 160ms both" }}>
        Six steps take a company from raw filings to a graph of contradictions — each traced
        back to a verbatim quote. <strong>Click a step to see what happens.</strong></p>
      <div style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--inkFaint)", marginBottom: 22,
        animation: "fadeUp 600ms ease 240ms both" }}>
        {stats ? `Live now: ${stats.companies} companies · ${stats.claims} claims indexed · ` : ""}
        a new company processes live in about 3–5 minutes — roughly a coffee run ☕.
      </div>

      {/* Interactive pipeline */}
      <div style={{ border: "1px solid var(--hairline)", borderRadius: 14, background: "var(--paperCard)",
        padding: "18px 16px 8px", overflowX: "auto", animation: "scaleIn 500ms cubic-bezier(.2,.8,.2,1) both" }}>
        <svg viewBox={`0 0 ${W} 178`} width="100%" style={{ minWidth: 760, display: "block" }}>
          <defs>
            <marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
              <path d="M0,0 L6,3 L0,6 Z" fill="var(--inkFaint)" />
            </marker>
          </defs>
          <text x={xs[0] + w / 2} y="30" textAnchor="middle" fontFamily="IBM Plex Mono, monospace"
            fontSize="10" fill="var(--inkSoft)">SEC filings · synthetic calls</text>
          <line x1={xs[0] + w / 2} y1="36" x2={xs[0] + w / 2} y2={Y - 4}
            stroke="var(--inkFaint)" strokeWidth="1.5" markerEnd="url(#arrow)" />

          {STAGES.map((st, i) => {
            const isActive = i === active;
            const isHover = i === hovered;
            const lift = isActive || isHover ? 3 : 0;
            return (
              <g key={st.title} style={{ cursor: "pointer", animation: `nodeIn 450ms ease ${i * 90}ms both` }}
                onClick={() => setActive(i)}
                onMouseEnter={() => setHovered(i)} onMouseLeave={() => setHovered(-1)}>
                {i > 0 && (
                  <line x1={xs[i - 1] + w} y1={cy} x2={xs[i] - 2} y2={cy}
                    stroke="var(--inkFaint)" strokeWidth="1.5" markerEnd="url(#arrow)" />
                )}
                {isActive && (
                  <rect x={xs[i] - 5} y={Y - 5 - lift} width={w + 10} height={H + 10} rx="13"
                    fill="none" stroke="var(--accent)" strokeWidth="2.5" />
                )}
                <rect x={xs[i]} y={Y - lift} width={w} height={H} rx="10"
                  fill={st.llm ? "var(--ink)" : "var(--paperCard)"} stroke="var(--ink)" strokeWidth="1.5"
                  style={{ transition: "y 140ms ease" }} />
                <text x={xs[i] + w / 2} y={cy - 3 - lift} textAnchor="middle"
                  fontFamily="Source Serif 4, serif" fontSize="15" fontWeight="600"
                  fill={st.llm ? "var(--paperCard)" : "var(--ink)"} style={{ pointerEvents: "none" }}>{st.title}</text>
                <text x={xs[i] + w / 2} y={cy + 14 - lift} textAnchor="middle"
                  fontFamily="IBM Plex Mono, monospace" fontSize="9"
                  fill={st.llm ? "var(--paperCard)" : "var(--inkFaint)"} style={{ pointerEvents: "none" }}>
                  {i + 1}{st.llm ? " · LLM" : ""}</text>
                {isActive && (
                  <path d={`M ${xs[i] + w / 2 - 7} ${Y + H + 6} L ${xs[i] + w / 2 + 7} ${Y + H + 6} L ${xs[i] + w / 2} ${Y + H + 16} Z`}
                    fill="var(--accent)" />
                )}
              </g>
            );
          })}

          <text x={xs[3] + w / 2} y={Y + H + 30} textAnchor="middle" fontFamily="IBM Plex Mono, monospace"
            fontSize="10" fill="var(--inkSoft)">Neo4j graph · Qdrant vectors</text>
        </svg>

        {/* Controls */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 14,
          padding: "6px 8px 10px" }}>
          <button onClick={prev} disabled={active === 0} style={ctlBtn(active === 0)}>← Prev</button>
          <div style={{ display: "flex", gap: 6 }}>
            {STAGES.map((_, i) => (
              <span key={i} onClick={() => setActive(i)} style={{ width: 8, height: 8, borderRadius: "50%",
                cursor: "pointer", background: i === active ? "var(--accent)" : "var(--hairline)" }} />
            ))}
          </div>
          <button onClick={next} disabled={active === STAGES.length - 1}
            style={ctlBtn(active === STAGES.length - 1)}>Next →</button>
        </div>
      </div>

      {/* Active-stage detail — re-animates on change */}
      <div key={active} style={{ marginTop: 18, border: "1px solid var(--hairline)", borderRadius: 14,
        background: "var(--paperCard)", padding: "28px 30px", animation: "fadeUp 380ms ease both" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 14 }}>
          <span style={{ width: 30, height: 30, borderRadius: "50%",
            background: s.llm ? "var(--ink)" : "var(--accent)", color: "var(--paperCard)",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontFamily: "var(--font-mono)", fontSize: 14 }}>{active + 1}</span>
          <span style={{ fontFamily: "var(--font-serif)", fontSize: 26, fontWeight: 600, color: "var(--ink)" }}>{s.title}</span>
          {s.llm && <span style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--accent)",
            border: "1px solid var(--accent)", borderRadius: 999, padding: "2px 8px" }}>AI step</span>}
        </div>
        <p style={{ fontFamily: "var(--font-serif)", fontSize: 19, lineHeight: 1.55, color: "var(--ink)",
          margin: "0 0 12px", maxWidth: 720 }}>{s.plain}</p>
        <p style={{ fontSize: 14, color: "var(--inkSoft)", lineHeight: 1.6, margin: "0 0 16px", maxWidth: 720 }}>{s.body}</p>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {s.tech.map((t) => (
            <span key={t} style={{ fontFamily: "var(--font-mono)", fontSize: 11, padding: "3px 10px",
              borderRadius: 999, border: "1px solid var(--hairline)", color: "var(--inkSoft)" }}>{t}</span>
          ))}
        </div>
      </div>

      {/* Trust callout */}
      <div style={{ marginTop: 28, border: "1px solid var(--hairline)", borderRadius: 14,
        background: "var(--accentSoft)", padding: "24px 26px", animation: "fadeUp 500ms ease 300ms both" }}>
        <div style={{ fontFamily: "var(--font-serif)", fontSize: 20, fontWeight: 600, color: "var(--ink)", marginBottom: 14 }}>
          Why you can trust it</div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 18 }}>
          {[
            ["Verbatim quote-spans", "Every claim carries an exact substring of its source, enforced by a guardrail — no paraphrase, no hallucinated quotes."],
            ["Real vs synthetic, always tagged", "Real SEC filings and synthetic earnings-call excerpts are clearly distinguished everywhere in the UI."],
            ["Fully traceable", "Every LLM call in a run is traced (Langfuse), and every claim links back to a rendered citation of its source."],
          ].map(([h, b]) => (
            <div key={h}>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--accent)", marginBottom: 6 }}>{h}</div>
              <div style={{ fontSize: 13, color: "var(--inkSoft)", lineHeight: 1.55 }}>{b}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function ctlBtn(disabled) {
  return {
    padding: "6px 14px", borderRadius: 999, border: "1px solid var(--hairline)",
    background: "transparent", color: disabled ? "var(--inkFaint)" : "var(--ink)",
    fontFamily: "var(--font-mono)", fontSize: 12, cursor: disabled ? "default" : "pointer",
    opacity: disabled ? 0.5 : 1,
  };
}
