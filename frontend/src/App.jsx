import { useEffect, useMemo, useState } from "react";
import { api, fmtDate, SEV, SEV_ORDER } from "./api.js";
import Header from "./components/Header.jsx";
import Landing from "./components/Landing.jsx";
import Processing from "./components/Processing.jsx";
import HowItWorks from "./components/HowItWorks.jsx";
import GraphView from "./components/GraphView.jsx";
import WorkspaceSearch from "./components/WorkspaceSearch.jsx";
import CitationDrawer from "./components/CitationDrawer.jsx";
import CompareModal from "./components/CompareModal.jsx";
import ChatPanel from "./components/ChatPanel.jsx";
import SummaryPanel from "./components/SummaryPanel.jsx";
import CitationCard from "./components/CitationCard.jsx";

export default function App() {
  const [companies, setCompanies] = useState([]);
  const [company, setCompany] = useState(null);
  const [view, setView] = useState("landing");
  const [topics, setTopics] = useState([]);
  const [activeTopicId, setActiveTopicId] = useState(null);
  const [claims, setClaims] = useState([]);
  const [contradictions, setContradictions] = useState([]);
  const [graphOpen, setGraphOpen] = useState(false);
  const [citation, setCitation] = useState(null);
  const [citationLoading, setCitationLoading] = useState(false);
  const [comparePair, setComparePair] = useState(null);
  const [chatOpen, setChatOpen] = useState(false);
  const [summaryOpen, setSummaryOpen] = useState(false);
  const [shareContradiction, setShareContradiction] = useState(null);
  const [processingCompany, setProcessingCompany] = useState(null);
  const [loadingWs, setLoadingWs] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.companies().then(setCompanies).catch(() => {});
  }, []);

  function handleOpen(c) {
    if (c.processed || c.claims) enterCompany(c);
    else { setProcessingCompany(c); setView("processing"); }
  }

  async function enterCompany(c) {
    setCompany(c);
    setView("workspace");
    setGraphOpen(false);
    setActiveTopicId(null);
    setTopics([]);
    setContradictions([]);
    setLoadingWs(true);
    try {
      const [tps, cons] = await Promise.all([
        api.topics(c.ticker),
        api.contradictions(c.ticker, "low"),
      ]);
      setTopics(tps);
      setContradictions(cons);
      setActiveTopicId(tps[0] && tps[0].topic);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoadingWs(false);
    }
  }

  useEffect(() => {
    if (!company || !activeTopicId) return;
    api.claims(activeTopicId, company.ticker).then(setClaims).catch((e) => setError(String(e)));
  }, [company, activeTopicId]);

  async function openCitation(claimId) {
    setCitationLoading(true);
    setCitation({ __open: true });
    try {
      const c = await api.citation(claimId);
      setCitation(c);
    } catch (e) {
      setError(String(e));
      setCitation(null);
    } finally {
      setCitationLoading(false);
    }
  }

  function openClaimResult(r) {
    // In-workspace semantic search result: jump to its topic + open the citation.
    setActiveTopicId(r.topic);
    openCitation(r.claim_id);
  }

  // Contradiction lookups
  const contraByClaim = useMemo(() => {
    const m = {};
    for (const c of contradictions) { m[c.a_id] = c; m[c.b_id] = c; }
    return m;
  }, [contradictions]);

  const maxSevByTopic = useMemo(() => {
    const m = {};
    for (const c of contradictions) {
      if (!m[c.topic] || SEV_ORDER[c.severity] > SEV_ORDER[m[c.topic]]) m[c.topic] = c.severity;
    }
    return m;
  }, [contradictions]);

  const activeTopic = topics.find((t) => t.topic === activeTopicId);
  const topicEdges = contradictions.filter((c) => c.topic === activeTopicId);

  if (error) {
    return <div style={{ padding: 40, fontFamily: "var(--font-mono)", color: "var(--sev-high)" }}>
      API error: {error}<br /><span style={{ color: "var(--inkSoft)" }}>
      Is the backend running? <code>uvicorn api.app:app --port 8000</code></span></div>;
  }

  return (
    <div style={{ minHeight: "100vh" }}>
      <Header company={view === "workspace" ? company : null}
        onNewSearch={() => { setView("landing"); setGraphOpen(false); setChatOpen(false); setSummaryOpen(false); }}
        onHowItWorks={() => setView("how")} />

      {view === "landing" && <Landing onOpen={handleOpen} />}

      {view === "how" && <HowItWorks onBack={() => setView("landing")} />}

      {view === "processing" && processingCompany && (
        <Processing company={processingCompany}
          onDone={(c) => enterCompany({ ...c, processed: true })}
          onBack={() => setView("landing")} />
      )}

      {view === "workspace" && loadingWs && (
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center",
          justifyContent: "center", minHeight: "calc(100vh - 68px)", gap: 14,
          color: "var(--inkSoft)" }}>
          <div style={{ width: 26, height: 26, borderRadius: "50%",
            border: "3px solid var(--hairline)", borderTopColor: "var(--accent)",
            animation: "spin 800ms linear infinite" }} />
          <div style={{ fontFamily: "var(--font-mono)", fontSize: 13 }}>
            Loading {company?.name || company?.ticker}…</div>
        </div>
      )}

      {view === "workspace" && !loadingWs && (
        <div style={{ display: "grid", gridTemplateColumns: "280px 1fr",
          minHeight: "calc(100vh - 68px)", animation: "fadeIn 450ms ease both" }}>
          {/* Sidebar */}
          <div style={{ borderRight: "1px solid var(--hairline)", padding: "28px 20px" }}>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, letterSpacing: ".1em",
              textTransform: "uppercase", color: "var(--inkFaint)", marginBottom: 16 }}>Topics</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              {topics.map((t) => {
                const sev = maxSevByTopic[t.topic];
                const active = t.topic === activeTopicId;
                return (
                  <div key={t.topic} onClick={() => { setActiveTopicId(t.topic); setGraphOpen(false); }}
                    style={{ display: "flex", alignItems: "center", justifyContent: "space-between",
                      gap: 8, padding: "10px 12px", borderRadius: 8, cursor: "pointer",
                      background: active ? "var(--accentSoft)" : "transparent" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <span style={{ width: 7, height: 7, borderRadius: "50%", flexShrink: 0,
                        background: sev ? SEV[sev] : "transparent",
                        border: sev ? "none" : "1px solid var(--hairline)" }} />
                      <span style={{ fontSize: 14, fontWeight: active ? 600 : 500, color: "var(--ink)" }}>
                        {t.name}</span>
                    </div>
                    <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--inkFaint)" }}>
                      {t.claims}</span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Main */}
          <div style={{ padding: "32px 40px 60px", maxWidth: 920 }}>
            <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between",
              gap: 16, marginBottom: 8, flexWrap: "wrap", animation: "fadeUp 400ms ease both" }}>
              <div>
                <h2 style={{ fontFamily: "var(--font-serif)", fontSize: 28, margin: "0 0 6px", color: "var(--ink)" }}>
                  {activeTopic?.name || "…"}</h2>
                <p style={{ fontSize: 14, color: "var(--inkSoft)", margin: 0, maxWidth: 520 }}>
                  {activeTopic?.description || ""}</p>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 12, flexShrink: 0 }}>
              <WorkspaceSearch ticker={company?.ticker} onResult={openClaimResult} />
              <button onClick={() => setSummaryOpen(true)}
                style={{ display: "flex", alignItems: "center", gap: 8, padding: "9px 16px",
                  borderRadius: 999, border: "1px solid var(--hairline)", background: "transparent",
                  color: "var(--ink)", fontSize: 12, cursor: "pointer", whiteSpace: "nowrap" }}>
                Summary</button>
              <button onClick={() => setGraphOpen((v) => !v)}
                style={{ display: "flex", alignItems: "center", gap: 8, padding: "9px 16px",
                  borderRadius: 999, border: "1px solid var(--ink)",
                  background: graphOpen ? "var(--ink)" : "transparent",
                  color: graphOpen ? "var(--paperCard)" : "var(--ink)", fontSize: 12,
                  cursor: "pointer", whiteSpace: "nowrap" }}>
                {graphOpen ? "Hide graph" : "View graph"}</button>
              <button onClick={() => setChatOpen(true)}
                style={{ display: "flex", alignItems: "center", gap: 8, padding: "9px 16px",
                  borderRadius: 999, border: "none", background: "var(--accent)",
                  color: "#fff", fontSize: 12, cursor: "pointer", whiteSpace: "nowrap" }}>
                Ask Counterpoint</button>
              </div>
            </div>

            {graphOpen && (
              <GraphView topicName={activeTopic?.name || ""}
                topicLabel={(activeTopic?.name || "").split(" ")[0]} claims={claims}
                edges={topicEdges} onOpenCitation={openCitation}
                onOpenCompare={(e) => setComparePair(e)} />
            )}

            <div style={{ display: "flex", flexDirection: "column", gap: 16, marginTop: 24 }}>
              {claims.map((c, i) => {
                const contra = contraByClaim[c.claim_id];
                const synthetic = c.source === "synthetic";
                return (
                  <div key={c.claim_id} style={{ background: "var(--paperCard)",
                    border: synthetic ? "1px dashed var(--hairline)" : "1px solid var(--hairline)",
                    borderRadius: 12, padding: "20px 22px",
                    animation: `fadeUp 500ms ease ${i * 70}ms both` }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
                      <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--inkFaint)" }}>
                        {fmtDate(c.date)}</span>
                      <span style={{ width: 4, height: 4, borderRadius: "50%", background: "var(--hairline)" }} />
                      <span style={synthetic
                        ? { padding: "2px 8px", borderRadius: 999, border: "1px dashed var(--inkFaint)",
                            fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--inkSoft)" }
                        : { padding: "2px 8px", borderRadius: 999, background: "var(--ink)",
                            fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--paperCard)" }}>
                        {synthetic ? `${c.doc_type} · synthetic` : c.doc_type}</span>
                    </div>
                    <div style={{ fontFamily: "var(--font-serif)", fontSize: 19, lineHeight: 1.5,
                      marginBottom: 14, color: "var(--ink)" }}>“{c.quote}”</div>
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between",
                      flexWrap: "wrap", gap: 10 }}>
                      <div style={{ fontSize: 13, color: "var(--inkSoft)" }}>
                        {c.speaker}{c.role ? ` · ${c.role}` : ""}</div>
                      <div style={{ display: "flex", gap: 8 }}>
                        {contra && (
                          <button onClick={() => setComparePair(contra)}
                            style={{ display: "flex", alignItems: "center", gap: 6, padding: "5px 10px",
                              borderRadius: 999, border: `1px solid ${SEV[contra.severity]}`,
                              background: `color-mix(in oklch, ${SEV[contra.severity]} 15%, var(--paper))`,
                              color: SEV[contra.severity], fontFamily: "var(--font-mono)", fontSize: 11,
                              cursor: "pointer" }}>
                            Contradiction · {contra.severity}</button>
                        )}
                        <button onClick={() => openCitation(c.claim_id)}
                          style={{ padding: "5px 10px", borderRadius: 999, border: "1px solid var(--hairline)",
                            background: "var(--paperCard)", color: "var(--ink)",
                            fontFamily: "var(--font-mono)", fontSize: 11, cursor: "pointer" }}>
                          View source →</button>
                      </div>
                    </div>
                  </div>
                );
              })}
              {claims.length === 0 && (
                <div style={{ color: "var(--inkFaint)", fontSize: 14 }}>No claims for this topic.</div>
              )}
            </div>
          </div>
        </div>
      )}

      {citation && (
        <CitationDrawer citation={citation.__open ? null : citation} loading={citationLoading}
          onClose={() => setCitation(null)} />
      )}
      {comparePair && (
        <CompareModal contradiction={comparePair} onClose={() => setComparePair(null)}
          onShare={(c) => setShareContradiction(c)} />
      )}
      {shareContradiction && (
        <CitationCard contradiction={shareContradiction} company={company}
          onClose={() => setShareContradiction(null)} />
      )}

      <ChatPanel open={chatOpen} onClose={() => setChatOpen(false)} company={company}
        onOpenCitation={openCitation} />
      <SummaryPanel open={summaryOpen} onClose={() => setSummaryOpen(false)} company={company}
        onOpenCitation={openCitation} />
    </div>
  );
}
