import { useEffect, useMemo, useState } from "react";
import { fmtDate } from "../api.js";

const CX = 240, CY = 190, R = 135;
const RAW = { high: "#c0392b", medium: "#c98a2c", low: "#3f7d54" };

export default function GraphView({ topicName, topicLabel, claims, edges, onOpenCitation, onOpenCompare }) {
  const [revealed, setRevealed] = useState(false);
  const [hover, setHover] = useState(null); // {kind:'node'|'edge', ...}

  useEffect(() => {
    setRevealed(false);
    const t = setTimeout(() => setRevealed(true), 60);
    return () => clearTimeout(t);
  }, [topicName, claims.length]);

  const claimById = useMemo(() => {
    const m = {};
    for (const c of claims) m[c.claim_id] = c;
    return m;
  }, [claims]);

  const { nodes, nodeMap } = useMemo(() => {
    const n = Math.max(claims.length, 1);
    const map = {};
    const arr = claims.map((c, i) => {
      const angle = (i / n) * Math.PI * 2 - Math.PI / 2;
      const node = { id: c.claim_id, x: CX + R * Math.cos(angle), y: CY + R * Math.sin(angle),
        synthetic: c.source === "synthetic" };
      map[c.claim_id] = node;
      return node;
    });
    return { nodes: arr, nodeMap: map };
  }, [claims]);

  const contraEdges = edges
    .map((e) => {
      const a = nodeMap[e.a_id], b = nodeMap[e.b_id];
      if (!a || !b) return null;
      const dx = b.x - a.x, dy = b.y - a.y;
      const len = Math.round(Math.sqrt(dx * dx + dy * dy));
      return { ...e, key: e.a_id + e.b_id, a, b, len,
        w: e.severity === "high" ? 4 : e.severity === "medium" ? 3 : 2 };
    })
    .filter(Boolean);

  const nContra = contraEdges.length;

  return (
    <div style={{ margin: "20px 0 8px", border: "1px solid var(--hairline)", borderRadius: 14,
      background: "var(--paperCard)", padding: 24, animation: "scaleIn 380ms cubic-bezier(.2,.8,.2,1) both" }}>

      {/* What this is */}
      <div style={{ display: "flex", alignItems: "flex-start", gap: 8, marginBottom: 14,
        fontSize: 13, color: "var(--inkSoft)", lineHeight: 1.5 }}>
        <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--accent)",
          textTransform: "uppercase", letterSpacing: ".1em", whiteSpace: "nowrap", paddingTop: 1 }}>
          How to read</span>
        <span>
          Each dot is a <strong>claim</strong> on this topic (filled = SEC filing, outlined =
          earnings call). A <span style={{ color: RAW.high, fontWeight: 600 }}>red line</span> joins
          two claims that <strong>contradict</strong> each other — thicker means higher severity.
          {nContra > 0
            ? " Hover any dot or line to inspect it; click a dot for its source, or a red line to compare the two claims."
            : " No contradictions were detected on this topic — the claims are consistent over time."}
        </span>
      </div>

      <svg viewBox="0 0 480 380" width="100%" height="360" style={{ overflow: "visible", display: "block" }}>
        {nodes.map((nd) => (
          <line key={"s" + nd.id} x1={CX} y1={CY} x2={nd.x} y2={nd.y} stroke="var(--hairline)" strokeWidth="1.5" />
        ))}
        {contraEdges.map((e) => {
          const active = hover?.kind === "edge" && hover.key === e.key;
          return (
            <line key={"c" + e.key} x1={e.a.x} y1={e.a.y} x2={e.b.x} y2={e.b.y}
              stroke={RAW[e.severity]} strokeWidth={active ? e.w + 2 : e.w}
              strokeDasharray={e.len} strokeDashoffset={revealed ? 0 : e.len}
              style={{ cursor: "pointer", transition: "stroke-dashoffset 900ms ease, stroke-width 120ms ease" }}
              onMouseEnter={() => setHover({ kind: "edge", key: e.key, edge: e })}
              onMouseLeave={() => setHover(null)}
              onClick={() => onOpenCompare(e)} />
          );
        })}
        <circle cx={CX} cy={CY} r="27" fill="var(--ink)">
          <title>{`Topic: ${topicName} — ${claims.length} claims`}</title>
        </circle>
        <text x={CX} y={CY + 4} textAnchor="middle" fill="var(--paperCard)"
          fontFamily="Source Serif 4, serif" fontSize="11" fontWeight="600"
          style={{ pointerEvents: "none" }}>{topicLabel}</text>
        {nodes.map((nd) => {
          const active = hover?.kind === "node" && hover.id === nd.id;
          return (
            <circle key={nd.id} cx={nd.x} cy={nd.y} r={active ? 18 : 15}
              fill={nd.synthetic ? "var(--paperCard)" : "var(--ink)"} stroke="var(--ink)"
              strokeWidth={nd.synthetic ? 2 : (active ? 2 : 0)}
              strokeDasharray={nd.synthetic ? "3,3" : "0"}
              style={{ cursor: "pointer", transition: "r 120ms ease" }}
              onMouseEnter={() => setHover({ kind: "node", id: nd.id })}
              onMouseLeave={() => setHover(null)}
              onClick={() => onOpenCitation(nd.id)} />
          );
        })}
      </svg>

      {/* Inspector: updates on hover, otherwise a hint */}
      <div style={{ minHeight: 66, borderTop: "1px solid var(--hairline)", marginTop: 8, paddingTop: 12 }}>
        {hover?.kind === "node" && claimById[hover.id] && (() => {
          const c = claimById[hover.id];
          return (
            <div>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--inkFaint)", marginBottom: 4 }}>
                {c.source === "synthetic" ? "Earnings call (synthetic)" : `${c.doc_type} (filing)`} · {fmtDate(c.date)} · {c.speaker}
              </div>
              <div style={{ fontFamily: "var(--font-serif)", fontSize: 15, color: "var(--ink)", lineHeight: 1.4 }}>
                “{c.quote.slice(0, 150)}{c.quote.length > 150 ? "…" : ""}” <span style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--accent)" }}>click to view source →</span>
              </div>
            </div>
          );
        })()}
        {hover?.kind === "edge" && (() => {
          const e = hover.edge;
          return (
            <div>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: RAW[e.severity], marginBottom: 4 }}>
                Contradiction · {e.severity} severity · click to compare
              </div>
              <div style={{ fontSize: 13, color: "var(--inkSoft)", lineHeight: 1.4 }}>
                {e.a_speaker} ({fmtDate(e.a_date)}) vs {e.b_speaker} ({fmtDate(e.b_date)})
              </div>
            </div>
          );
        })()}
        {!hover && (
          <div style={{ display: "flex", gap: 18, flexWrap: "wrap", alignItems: "center" }}>
            <Legend swatch={<span style={{ width: 12, height: 12, borderRadius: "50%", background: "var(--ink)", display: "inline-block" }} />} label="Filing (real)" />
            <Legend swatch={<span style={{ width: 12, height: 12, borderRadius: "50%", background: "var(--paperCard)", border: "2px dashed var(--ink)", display: "inline-block" }} />} label="Earnings call (synthetic)" />
            {[["High", RAW.high], ["Medium", RAW.medium], ["Low", RAW.low]].map(([l, col]) => (
              <Legend key={l} swatch={<span style={{ width: 16, height: 3, background: col, display: "inline-block" }} />} label={l} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function Legend({ swatch, label }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6, fontFamily: "var(--font-mono)",
      fontSize: 11, color: "var(--inkSoft)" }}>
      {swatch}{label}
    </div>
  );
}
