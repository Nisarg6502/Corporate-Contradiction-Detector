import { useEffect, useState } from "react";

// Full-screen boot loader. The animation is the product's thesis in miniature:
// a filing is "scanned", two opposing claims are traced in from either side,
// and where they meet a contradiction sparks. Cycles a short line of copy that
// mirrors the real pipeline (read → trace → detect) so the wait tells a story.
const PHASES = [
  "Reading the filings",
  "Tracing every claim",
  "Finding the contradictions",
];

export default function AppLoader({ leaving }) {
  const [phase, setPhase] = useState(0);

  useEffect(() => {
    const t = setInterval(() => setPhase((p) => (p + 1) % PHASES.length), 1400);
    return () => clearInterval(t);
  }, []);

  return (
    <div
      style={{
        position: "fixed", inset: 0, zIndex: 200, background: "var(--paper)",
        display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
        gap: 30, textAlign: "center",
        animation: leaving ? "bootOut 480ms var(--ease-out) both" : "fadeIn 300ms ease both",
        pointerEvents: leaving ? "none" : "auto",
      }}
    >
      {/* Wordmark */}
      <div style={{ display: "flex", alignItems: "center", gap: 12, animation: "fadeUp 700ms var(--ease-out) both" }}>
        <div style={{
          width: 34, height: 34, borderRadius: 8, background: "var(--ink)",
          display: "flex", alignItems: "center", justifyContent: "center", position: "relative",
        }}>
          <div style={{
            width: 12, height: 12, borderRadius: "50%", background: "var(--accent)",
            animation: "glowPulse 1.8s ease-in-out infinite",
          }} />
        </div>
        <span style={{
          fontFamily: "var(--font-serif)", fontWeight: 600, fontSize: 26,
          letterSpacing: ".01em", color: "var(--ink)",
        }}>Counterpoint</span>
      </div>

      {/* The scanning + contradiction animation */}
      <ScanArt />

      {/* Cycling phase copy */}
      <div style={{ height: 20, position: "relative", width: 280 }}>
        {PHASES.map((p, i) => (
          <div
            key={p}
            style={{
              position: "absolute", inset: 0, fontFamily: "var(--font-mono)", fontSize: 12.5,
              letterSpacing: ".06em", color: "var(--inkSoft)",
              opacity: phase === i ? 1 : 0,
              transform: phase === i ? "translateY(0)" : "translateY(6px)",
              transition: "opacity 450ms var(--ease-out), transform 450ms var(--ease-out)",
            }}
          >
            {p}<span style={{ opacity: .6 }}>…</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function ScanArt() {
  return (
    <svg width="260" height="150" viewBox="0 0 260 150" fill="none"
      style={{ animation: "fadeIn 900ms ease 200ms both", overflow: "visible" }}>
      {/* Document sheet */}
      <rect x="70" y="16" width="120" height="118" rx="8"
        fill="var(--paperCard)" stroke="var(--hairline)" strokeWidth="1.5" />

      {/* Text lines on the sheet */}
      {[30, 42, 54, 78, 90, 102, 114].map((y, i) => (
        <rect key={y} x="84" y={y} width={i % 3 === 0 ? 92 : i % 3 === 1 ? 74 : 60} height="4" rx="2"
          fill="var(--hairline)"
          style={{ opacity: 0, animation: `fadeIn 500ms ease ${300 + i * 90}ms both` }} />
      ))}

      {/* Scanning line sweeping the sheet */}
      <g style={{ animation: "scanSweep 2.1s var(--ease-inout) infinite", transformOrigin: "center" }}>
        <rect x="70" y="14" width="120" height="3" rx="1.5" fill="var(--accent)" opacity="0.9" />
        <rect x="70" y="14" width="120" height="22" fill="url(#scanGrad)" />
      </g>

      {/* Two opposing claims traced in from the sides toward a clash point */}
      <line x1="8" y1="75" x2="70" y2="75" stroke="var(--ink)" strokeWidth="2" strokeLinecap="round"
        strokeDasharray="62" style={{ "--dash": "62", animation: "drawLine 900ms var(--ease-out) 700ms both" }} />
      <line x1="252" y1="75" x2="190" y2="75" stroke="var(--ink)" strokeWidth="2" strokeLinecap="round"
        strokeDasharray="62" style={{ "--dash": "62", animation: "drawLine 900ms var(--ease-out) 700ms both" }} />
      <circle cx="8" cy="75" r="4" fill="var(--ink)"
        style={{ opacity: 0, animation: "popIn 400ms var(--ease-out) 760ms both" }} />
      <circle cx="252" cy="75" r="4" fill="var(--ink)"
        style={{ opacity: 0, animation: "popIn 400ms var(--ease-out) 760ms both" }} />

      {/* Contradiction spark where the claims meet the document */}
      <g style={{ transformOrigin: "130px 75px", animation: "sparkPop 600ms var(--ease-out) 1500ms both" }}>
        <circle cx="130" cy="75" r="13" fill="none" stroke="var(--accent)" strokeWidth="1.5"
          style={{ transformOrigin: "130px 75px", animation: "ringPulse 1.8s ease-out 1800ms infinite" }} />
        <circle cx="130" cy="75" r="9" fill="var(--accent)" />
        <path d="M126 71 l8 8 M134 71 l-8 8" stroke="#fff" strokeWidth="1.8" strokeLinecap="round" />
      </g>

      <defs>
        <linearGradient id="scanGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.18" />
          <stop offset="100%" stopColor="var(--accent)" stopOpacity="0" />
        </linearGradient>
      </defs>
    </svg>
  );
}
