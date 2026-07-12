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
  { title: "Serve", plain: "You get a timeline, a graph, hybrid search, an executive summary, a citation for every single claim — and a chat assistant to ask it all directly.",
    body: "A FastAPI backend and this React app surface it all, with book-page citations that trace each claim to its source. \"Ask Counterpoint\" is a LangGraph agent scoped to the open company: it calls the same graph/search tools, cites every claim it uses, and refuses off-topic questions, other companies, investment advice, and prompt injection.", tech: ["FastAPI", "React", "LangGraph", "gpt-oss (Ollama)"], llm: true },
];

const W = 1000, Y = 78, H = 56, w = 132;
const gap = (W - 6 * w) / 5;
const xs = STAGES.map((_, i) => i * (w + gap));
const cy = Y + H / 2;

export default function HowItWorks({ onBack }) {
  const [stats, setStats] = useState(null);
  const [active, setActive] = useState(0);
  const [hovered, setHovered] = useState(-1);
  const [view, setView] = useState("overview");

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

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end",
        flexWrap: "wrap", gap: 12 }}>
        <div style={{ fontFamily: "var(--font-mono)", fontSize: 12, letterSpacing: ".12em",
          textTransform: "uppercase", color: "var(--accent)", marginBottom: 12,
          animation: "fadeUp 600ms ease both" }}>How it works</div>
        <div style={{ display: "flex", gap: 6, marginBottom: 12 }}>
          <button onClick={() => setView("overview")} style={viewToggleBtn(view === "overview")}>
            Overview
          </button>
          <button onClick={() => setView("detailed")} style={viewToggleBtn(view === "detailed")}>
            Technical detail
          </button>
        </div>
      </div>

      {view === "overview" ? (
        <>
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
        </>
      ) : (
        <DetailedView />
      )}

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

function viewToggleBtn(active) {
  return {
    padding: "6px 14px", borderRadius: 999, cursor: "pointer",
    border: active ? "1px solid var(--accent)" : "1px solid var(--hairline)",
    background: active ? "var(--accentSoft)" : "transparent",
    color: active ? "var(--accent)" : "var(--inkSoft)",
    fontFamily: "var(--font-mono)", fontSize: 12,
  };
}

const pillStyle = {
  border: "1px solid var(--hairline)", borderRadius: 999, padding: "3px 10px",
  fontFamily: "var(--font-mono)", fontSize: 10.5, color: "var(--inkSoft)",
};

const sectionLabel = {
  fontFamily: "var(--font-mono)", fontSize: 12, letterSpacing: ".08em",
  textTransform: "uppercase", color: "var(--accent)", margin: "0 0 12px",
};

function ModelCard({ role, m }) {
  return (
    <div style={{ border: "1px solid var(--hairline)", borderRadius: 10, background: "var(--paperCard)",
      padding: "14px 16px" }}>
      <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, textTransform: "uppercase",
        letterSpacing: ".05em", color: "var(--accent)", marginBottom: 6 }}>{role}</div>
      <div style={{ fontFamily: "var(--font-serif)", fontSize: 15.5, color: "var(--ink)", marginBottom: 8,
        wordBreak: "break-word" }}>{m.model}</div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 5 }}>
        <span style={pillStyle}>{m.provider}</span>
        {m.temperature !== undefined && <span style={pillStyle}>temp {m.temperature}</span>}
        {m.max_tokens != null && <span style={pillStyle}>{m.max_tokens} max tokens</span>}
        {m.dimension != null && <span style={pillStyle}>{m.dimension}d vectors</span>}
        {m.reasoning === false && <span style={pillStyle}>reasoning off</span>}
      </div>
    </div>
  );
}

function DiagBox({ x, y, w, h, label, sub, dark }) {
  return (
    <g>
      <rect x={x} y={y} width={w} height={h} rx="8"
        fill={dark ? "var(--ink)" : "var(--paperCard)"} stroke="var(--ink)" strokeWidth="1.4" />
      <text x={x + w / 2} y={y + h / 2 - (sub ? 7 : 0)} textAnchor="middle" dominantBaseline="middle"
        fontFamily="Source Serif 4, serif" fontSize="12.5" fontWeight="600"
        fill={dark ? "var(--paperCard)" : "var(--ink)"}>{label}</text>
      {sub && (
        <text x={x + w / 2} y={y + h / 2 + 13} textAnchor="middle" dominantBaseline="middle"
          fontFamily="IBM Plex Mono, monospace" fontSize="8.7"
          fill={dark ? "var(--paperCard)" : "var(--inkFaint)"}>{sub}</text>
      )}
    </g>
  );
}

function DiagArrow({ x1, y1, x2, y2, dashed, markerId }) {
  return (
    <line x1={x1} y1={y1} x2={x2} y2={y2} stroke="var(--inkFaint)" strokeWidth="1.3"
      strokeDasharray={dashed ? "3,3" : undefined} markerEnd={`url(#${markerId})`} />
  );
}

function DiagLabel({ x, y, text, anchor = "middle" }) {
  return (
    <text x={x} y={y} textAnchor={anchor} fontFamily="IBM Plex Mono, monospace" fontSize="8.5"
      fill="var(--inkFaint)">{text}</text>
  );
}

function ArchitectureDiagram({ info }) {
  const ex = info.models.extraction.model;
  const jm = info.models.judgment.model;
  const em = info.models.embedding.model;
  return (
    <div style={{ border: "1px solid var(--hairline)", borderRadius: 14, background: "var(--paperCard)",
      padding: "20px 12px", overflowX: "auto" }}>
      <svg viewBox="0 0 680 600" width="100%" style={{ minWidth: 620, display: "block" }}>
        <defs>
          <marker id="arch-arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
            <path d="M0,0 L6,3 L0,6 Z" fill="var(--inkFaint)" />
          </marker>
        </defs>

        <DiagBox x={60} y={20} w={180} h={46} label="EDGAR filings" sub="real 10-K / 10-Q / 8-K" />
        <DiagBox x={440} y={20} w={180} h={46} label="Synthetic PDFs" sub="NVDA demo only" />
        <DiagArrow x1={150} y1={66} x2={290} y2={98} markerId="arch-arrow" />
        <DiagArrow x1={530} y1={66} x2={390} y2={98} markerId="arch-arrow" />

        <DiagBox x={240} y={100} w={200} h={46} label="Parse" sub="BeautifulSoup · PyMuPDF" />
        <DiagArrow x1={340} y1={146} x2={340} y2={178} markerId="arch-arrow" />

        <DiagBox x={230} y={180} w={220} h={52} label="Extract claims" sub={ex} dark />
        <DiagLabel x={340} y={244} text="verbatim quote-span guardrail" />
        <DiagArrow x1={280} y1={232} x2={180} y2={270} markerId="arch-arrow" />
        <DiagArrow x1={400} y1={232} x2={500} y2={270} markerId="arch-arrow" />

        <DiagBox x={70} y={270} w={220} h={50} label="Neo4j graph" sub="claims · speakers · topics · edges" />
        <DiagBox x={390} y={270} w={220} h={50} label="Qdrant vectors" sub={em} />

        <DiagArrow x1={180} y1={320} x2={180} y2={360} markerId="arch-arrow" />
        <DiagBox x={70} y={360} w={220} h={50} label="Detect contradictions" sub={jm} dark />
        <DiagLabel x={180} y={424} text="writes CONTRADICTS edges back" />

        <DiagArrow x1={220} y1={410} x2={300} y2={450} markerId="arch-arrow" />
        <DiagArrow x1={500} y1={320} x2={400} y2={450} markerId="arch-arrow" />
        <DiagBox x={230} y={450} w={220} h={50} label="FastAPI" sub="REST + SSE streaming, incl. chat agent" />

        <DiagArrow x1={340} y1={500} x2={340} y2={530} markerId="arch-arrow" />
        <DiagBox x={230} y={530} w={220} h={46} label="React UI" sub="chat · citations · graph · summary" />
      </svg>
    </div>
  );
}

function ChatGraphDiagram({ info }) {
  const orch = info.models.chat.orchestrator.model;
  const synth = info.models.chat.synthesis.model;
  const guard = info.models.chat.guardrail.model;
  return (
    <div style={{ border: "1px solid var(--hairline)", borderRadius: 14, background: "var(--paperCard)",
      padding: "20px 12px", overflowX: "auto" }}>
      <svg viewBox="0 0 700 400" width="100%" style={{ minWidth: 620, display: "block" }}>
        <defs>
          <marker id="chat-arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
            <path d="M0,0 L6,3 L0,6 Z" fill="var(--inkFaint)" />
          </marker>
        </defs>

        <DiagBox x={230} y={10} w={220} h={48} label="Input guardrail" sub={guard} dark />
        <DiagBox x={500} y={10} w={160} h={48} label="Refuse" sub="canned copy, no LLM" />
        <DiagArrow x1={450} y1={34} x2={498} y2={34} markerId="chat-arrow" />
        <DiagLabel x={474} y={24} text="blocked" />
        <DiagLabel x={580} y={78} text="→ END" />

        <DiagArrow x1={340} y1={58} x2={340} y2={90} markerId="chat-arrow" />
        <DiagLabel x={370} y={78} text="allowed" anchor="start" />
        <DiagBox x={230} y={90} w={220} h={50} label="Orchestrator" sub={orch} dark />

        {/* Tools loop sits off to the side so it never crosses the main
            orchestrator -> synthesizer line below. */}
        <DiagBox x={500} y={100} w={160} h={46} label="Tools" sub="6 ticker-locked tools" />
        <DiagArrow x1={450} y1={112} x2={498} y2={116} markerId="chat-arrow" />
        <DiagLabel x={475} y={102} text="tool_calls" />
        <DiagArrow x1={498} y1={138} x2={452} y2={133} dashed markerId="chat-arrow" />
        <DiagLabel x={580} y={168} text="collect_retrieved" />
        <DiagLabel x={580} y={179} text="loop ≤ 6" />

        <DiagArrow x1={340} y1={140} x2={340} y2={192} markerId="chat-arrow" />
        <DiagLabel x={372} y={160} text="no more" anchor="start" />
        <DiagLabel x={372} y={171} text="tool_calls" anchor="start" />
        <DiagBox x={230} y={192} w={220} h={50} label="Synthesizer" sub={synth} dark />

        <DiagArrow x1={340} y1={242} x2={340} y2={282} markerId="chat-arrow" />
        <DiagBox x={230} y={282} w={220} h={50} label="Output guardrail" sub="grounding + safety check" />
        <DiagArrow x1={228} y1={306} x2={228} y2={218} dashed markerId="chat-arrow" />
        <DiagLabel x={150} y={255} text="ungrounded," />
        <DiagLabel x={150} y={266} text="retry ≤ 1" />

        <DiagArrow x1={340} y1={332} x2={340} y2={362} markerId="chat-arrow" />
        <DiagLabel x={372} y={352} text="grounded → END" anchor="start" />
      </svg>
    </div>
  );
}

function DetailedView() {
  const [info, setInfo] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.systemInfo().then(setInfo).catch((e) => setError(e.message || "Failed to load system info."));
  }, []);

  return (
    <div style={{ animation: "fadeUp 380ms ease both" }}>
      <h1 style={{ fontFamily: "var(--font-serif)", fontSize: 32, lineHeight: 1.15, margin: "0 0 12px",
        color: "var(--ink)", maxWidth: 720 }}>Every model, every store, every guardrail.</h1>
      <p style={{ fontSize: 14.5, color: "var(--inkSoft)", lineHeight: 1.6, maxWidth: 700, margin: "0 0 28px" }}>
        Read live from <code>config/models.yaml</code> and <code>config/processing.yaml</code> via{" "}
        <code>GET /system/info</code> — nothing on this page is hardcoded, so it can't drift from
        what's actually running.
      </p>

      {error && (
        <div style={{ color: "var(--sev-high)", fontFamily: "var(--font-mono)", fontSize: 12 }}>{error}</div>
      )}
      {!info && !error && (
        <div style={{ color: "var(--inkFaint)", fontFamily: "var(--font-mono)", fontSize: 12 }}>Loading…</div>
      )}

      {info && (
        <>
          <div style={sectionLabel}>Model roster</div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
            gap: 12, marginBottom: 32 }}>
            <ModelCard role="Claim extraction" m={info.models.extraction} />
            <ModelCard role="Contradiction judgment" m={info.models.judgment} />
            <ModelCard role="Embeddings (semantic search)" m={info.models.embedding} />
            <ModelCard role="Chat — orchestrator" m={info.models.chat.orchestrator} />
            <ModelCard role="Chat — synthesis" m={info.models.chat.synthesis} />
            <ModelCard role="Chat — guardrail" m={info.models.chat.guardrail} />
          </div>

          <div style={sectionLabel}>Data pipeline architecture</div>
          <div style={{ marginBottom: 32 }}>
            <ArchitectureDiagram info={info} />
          </div>

          <div style={sectionLabel}>Chat agent graph (LangGraph)</div>
          <div style={{ marginBottom: 32 }}>
            <ChatGraphDiagram info={info} />
          </div>

          <div style={sectionLabel}>Processing bounds</div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {(info.processing.filings || []).map((f) => (
              <span key={f.form} style={pillStyle}>{f.limit}× {f.form}</span>
            ))}
            <span style={pillStyle}>{info.processing.max_chunks_per_doc} chunks / doc</span>
            <span style={pillStyle}>{info.processing.max_detection_pairs} detection pairs</span>
            <span style={pillStyle}>{info.topics.length} curated topics</span>
            <span style={pillStyle}>{info.chatbot.max_tool_iterations} max tool-call rounds / turn</span>
            <span style={pillStyle}>{info.chatbot.turn_timeout_seconds}s turn timeout</span>
            <span style={pillStyle}>{info.chatbot.rate_limit_per_minute} msgs / min / session</span>
          </div>
        </>
      )}
    </div>
  );
}
