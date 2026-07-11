import { fmtDate, SEV } from "../api.js";

function Side({ date, source, speaker, role, quote }) {
  return (
    <div style={{
      border: source === "synthetic" ? "1px dashed var(--hairline)" : "1px solid var(--hairline)",
      borderRadius: 12, padding: 20,
    }}>
      <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--inkFaint)", marginBottom: 10 }}>
        {fmtDate(date)} · {source === "synthetic" ? "Earnings Call · synthetic" : "Filing"}
      </div>
      <div style={{ fontFamily: "var(--font-serif)", fontSize: 17, lineHeight: 1.5, marginBottom: 10, color: "var(--ink)" }}>
        “{quote}”
      </div>
      <div style={{ fontSize: 12, color: "var(--inkSoft)" }}>
        {speaker}{role ? ` · ${role}` : ""}
      </div>
    </div>
  );
}

export default function CompareModal({ contradiction: c, onClose }) {
  const stop = (e) => e.stopPropagation();
  const color = SEV[c.severity];
  return (
    <div onClick={onClose} style={{
      position: "fixed", inset: 0, background: "rgba(20,18,14,0.4)", zIndex: 70,
      display: "flex", alignItems: "center", justifyContent: "center", padding: 40,
      animation: "fadeIn 250ms ease both",
    }}>
      <div onClick={stop} style={{
        background: "var(--paperCard)", borderRadius: 16, maxWidth: 920, width: "100%",
        padding: 36, boxShadow: "0 24px 60px rgba(0,0,0,.2)",
        animation: "popIn 380ms cubic-bezier(.2,.8,.2,1) both",
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
          <div style={{
            display: "inline-flex", alignItems: "center", gap: 6, padding: "6px 12px",
            borderRadius: 999, background: `color-mix(in oklch, ${color} 15%, var(--paper))`,
            color, fontFamily: "var(--font-mono)", fontSize: 11, fontWeight: 600,
          }}>Contradiction · {c.severity} severity</div>
          <button onClick={onClose} style={{ border: "none", background: "transparent", fontSize: 22,
            cursor: "pointer", color: "var(--inkSoft)", lineHeight: 1 }}>×</button>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr auto 1fr", gap: 20,
          alignItems: "center", margin: "24px 0" }}>
          <Side date={c.a_date} source={c.a_source} speaker={c.a_speaker} role={c.a_role} quote={c.a_quote} />
          <div style={{ fontFamily: "var(--font-serif)", fontSize: 22, fontStyle: "italic", color }}>vs</div>
          <Side date={c.b_date} source={c.b_source} speaker={c.b_speaker} role={c.b_role} quote={c.b_quote} />
        </div>

        <div style={{ paddingTop: 16, borderTop: "1px solid var(--hairline)" }}>
          <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, textTransform: "uppercase",
            letterSpacing: ".08em", color: "var(--inkFaint)", marginBottom: 8 }}>Judgment reasoning</div>
          <div style={{ fontSize: 14, lineHeight: 1.6, color: "var(--ink)" }}>{c.reasoning}</div>
        </div>
      </div>
    </div>
  );
}
