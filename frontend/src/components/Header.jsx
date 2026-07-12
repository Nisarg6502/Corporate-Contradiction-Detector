export default function Header({ company, onNewSearch, onHowItWorks }) {
  return (
    <div
      style={{
        position: "sticky", top: 0, zIndex: 40, display: "flex",
        alignItems: "center", justifyContent: "space-between", padding: "18px 32px",
        background: "var(--headerBg)", backdropFilter: "blur(10px)",
        borderBottom: "1px solid var(--hairline)",
      }}
    >
      <div
        onClick={onNewSearch}
        onMouseEnter={(e) => (e.currentTarget.style.transform = "translateY(-1px)")}
        onMouseLeave={(e) => (e.currentTarget.style.transform = "translateY(0)")}
        style={{ display: "flex", alignItems: "center", gap: 10, cursor: "pointer",
          transition: "transform 160ms var(--ease-out)" }}
      >
        <div style={{
          width: 28, height: 28, borderRadius: 6, background: "var(--ink)",
          display: "flex", alignItems: "center", justifyContent: "center",
        }}>
          <div style={{ width: 10, height: 10, borderRadius: "50%", background: "var(--accent)",
            animation: "glowPulse 3.2s ease-in-out infinite" }} />
        </div>
        <span style={{
          fontFamily: "var(--font-serif)", fontWeight: 600, fontSize: 18,
          letterSpacing: "0.01em", color: "var(--ink)",
        }}>Counterpoint</span>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
        {company && (
          <div style={{
            display: "flex", alignItems: "center", gap: 8, padding: "6px 12px",
            border: "1px solid var(--hairline)", borderRadius: 999,
            fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--inkSoft)",
            animation: "slideUpIn 360ms var(--ease-out) both",
          }}>
            <span style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--accent)",
              animation: "softPulse 2.4s ease-in-out infinite" }} />
            {company.name} · {company.ticker}
          </div>
        )}
        <button onClick={onHowItWorks} style={{ padding: "8px 12px", borderRadius: 999,
          border: "none", background: "transparent", color: "var(--inkSoft)",
          fontFamily: "var(--font-mono)", fontSize: 12, cursor: "pointer" }}>How it works</button>
        {company && (
          <button onClick={onNewSearch} style={{
            padding: "8px 14px", borderRadius: 999, border: "1px solid var(--ink)",
            background: "transparent", color: "var(--ink)", fontSize: 12, cursor: "pointer",
          }}>New search</button>
        )}
      </div>
    </div>
  );
}
