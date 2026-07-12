import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";
import { extractCitationOrder } from "../lib/citations.jsx";
import { renderMarkdown } from "../lib/markdown.jsx";

function fmtTime(ts) {
  if (!ts) return "";
  try {
    return new Date(ts).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  } catch {
    return "";
  }
}

const TOOL_LABELS = {
  list_topics: "Listing topics",
  get_claim_timeline: "Reading claim timeline",
  get_contradictions: "Checking contradictions",
  list_speakers: "Listing speakers",
  semantic_search: "Searching claims",
  get_citation: "Verifying citation",
};

function ToolIndicator({ tool }) {
  if (!tool) return null;
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 9, fontFamily: "var(--font-mono)",
      fontSize: 11, color: "var(--inkFaint)", padding: "4px 0",
      animation: "slideUpIn 300ms var(--ease-out) both",
    }}>
      <span className="cp-typing"><span /><span /><span /></span>
      {TOOL_LABELS[tool] || tool}…
    </div>
  );
}

function CitationChips({ claimIds, onOpenCitation }) {
  if (!claimIds || claimIds.length === 0) return null;
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 8 }}>
      {claimIds.map((id, i) => (
        <button
          key={id}
          className="cp-press"
          onClick={() => onOpenCitation(id)}
          style={{
            border: "1px solid var(--hairline)", borderRadius: 999, background: "var(--accentSoft)",
            color: "var(--accent)", fontFamily: "var(--font-mono)", fontSize: 10,
            padding: "3px 10px", cursor: "pointer",
            animation: `popIn 300ms var(--ease-out) ${i * 55}ms both`,
          }}
          title={id}
        >
          Source {i + 1}
        </button>
      ))}
    </div>
  );
}

function Bubble({ role, text, ts, onOpenCitation, pending }) {
  const isUser = role === "user";
  const order = isUser ? [] : extractCitationOrder(text);
  const showChips = !isUser && !pending && order.length > 0;
  return (
    <div style={{
      display: "flex", flexDirection: "column", alignItems: isUser ? "flex-end" : "flex-start",
      marginBottom: 14, animation: `${isUser ? "slideInRight" : "slideUpIn"} 320ms var(--ease-out) both`,
    }}>
      <div style={{
        maxWidth: "88%", padding: "12px 16px", borderRadius: 12,
        background: isUser ? "var(--accentSoft)" : "var(--paperCard)",
        border: isUser ? "1px solid transparent" : "1px solid var(--hairline)",
        fontFamily: "var(--font-serif)", fontSize: 15, lineHeight: 1.65, color: "var(--ink)",
        boxShadow: isUser ? "none" : "0 1px 2px rgba(20,35,46,.04)",
      }}>
        {isUser
          ? <span style={{ whiteSpace: "pre-wrap" }}>{text}</span>
          : text
            ? <>{renderMarkdown(text, order, onOpenCitation)}{pending && <span className="cp-caret" />}</>
            : (pending ? <span className="cp-typing"><span /><span /><span /></span> : "")}
        {showChips && <CitationChips claimIds={order} onOpenCitation={onOpenCitation} />}
      </div>
      {ts && (isUser || (text && text.trim())) && (
        <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--inkFaint)",
          margin: "4px 4px 0" }}>
          {fmtTime(ts)}
        </div>
      )}
    </div>
  );
}

function FollowupChips({ questions, onPick, disabled }) {
  if (!questions || questions.length === 0) return null;
  return (
    <div style={{ marginTop: 4, marginBottom: 8, animation: "slideUpIn 360ms var(--ease-out) both" }}>
      <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, letterSpacing: ".06em",
        textTransform: "uppercase", color: "var(--inkFaint)", marginBottom: 8, marginLeft: 2 }}>
        You might also ask
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
        {questions.map((q, i) => (
          <button
            key={q}
            onClick={() => onPick(q)}
            disabled={disabled}
            onMouseEnter={(e) => { if (!disabled) { e.currentTarget.style.borderColor = "var(--accent)"; e.currentTarget.style.background = "var(--accentSoft)"; } }}
            onMouseLeave={(e) => { e.currentTarget.style.borderColor = "var(--hairline)"; e.currentTarget.style.background = "var(--paperCard)"; }}
            style={{
              textAlign: "left", border: "1px solid var(--hairline)", borderRadius: 999,
              background: "var(--paperCard)", padding: "7px 13px",
              cursor: disabled ? "default" : "pointer",
              fontFamily: "var(--font-serif)", fontSize: 12.5, color: "var(--ink)",
              transition: "border-color 150ms ease, background-color 150ms ease",
              animation: `popIn 300ms var(--ease-out) ${i * 60}ms both`,
            }}>
            {q}
          </button>
        ))}
      </div>
    </div>
  );
}

export default function ChatPanel({ open, onClose, company, onOpenCitation }) {
  const [messages, setMessages] = useState([]);
  const [sessionId, setSessionId] = useState(null);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [activeTool, setActiveTool] = useState(null);
  const [suggestions, setSuggestions] = useState([]);
  const [followups, setFollowups] = useState([]);
  const [error, setError] = useState(null);
  const [lastMessage, setLastMessage] = useState("");
  const scrollRef = useRef(null);
  const ticker = company?.ticker;

  // Reset conversation when the open company changes.
  useEffect(() => {
    setMessages([]);
    setSessionId(null);
    setError(null);
    setLastMessage("");
    setSuggestions([]);
    setFollowups([]);
    if (!ticker) return;
    api.chatSuggestions(ticker).then((r) => setSuggestions(r.questions || [])).catch(() => {});
  }, [ticker]);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, activeTool, followups]);

  async function runTurn(trimmed) {
    setStreaming(true);
    setActiveTool(null);
    setFollowups([]);
    let finalAnswer = "";

    const updateLastAssistant = (patch) =>
      setMessages((m) => {
        const next = [...m];
        const last = next[next.length - 1];
        next[next.length - 1] = { ...last, ...patch(last) };
        return next;
      });

    try {
      await api.chatStream(ticker, sessionId, trimmed, {
        session: (d) => setSessionId(d.session_id),
        tool: (d) => setActiveTool(d.status === "start" ? d.name : null),
        token: (d) => {
          finalAnswer += d.text;
          updateLastAssistant((last) => ({ text: (last.text || "") + d.text, ts: last.ts || Date.now() }));
        },
        retry: () => { finalAnswer = ""; updateLastAssistant(() => ({ text: "" })); },
        citation: () => {},
        error: (d) => setError(d.message),
        done: (d) => {
          if (d.answer) finalAnswer = d.answer;
          updateLastAssistant((last) => ({ text: last.text || d.answer || "", ts: last.ts || Date.now() }));
        },
      });
    } catch (e) {
      setError(e.message || "Something went wrong.");
    } finally {
      setStreaming(false);
      setActiveTool(null);
    }

    // Generate follow-up suggestions AFTER the answer is shown, so this extra
    // (fast, small-model) call never delays the answer itself. Best-effort.
    if (finalAnswer.trim()) {
      api.chatFollowups(ticker, trimmed, finalAnswer)
        .then((r) => setFollowups(r.questions || []))
        .catch(() => {});
    }
  }

  async function send(text) {
    const trimmed = text.trim();
    if (!trimmed || !ticker || streaming) return;
    setError(null);
    setInput("");
    setLastMessage(trimmed);
    setMessages((m) => [...m, { role: "user", text: trimmed, ts: Date.now() }, { role: "assistant", text: "" }]);
    await runTurn(trimmed);
  }

  async function retry() {
    if (!lastMessage || !ticker || streaming) return;
    setError(null);
    setMessages((m) => {
      const next = m[m.length - 1]?.role === "assistant" ? m.slice(0, -1) : m;
      return [...next, { role: "assistant", text: "" }];
    });
    await runTurn(lastMessage);
  }

  if (!open) return null;

  return (
    <div onClick={onClose} style={{
      position: "fixed", inset: 0, background: "rgba(20,18,14,0.28)", zIndex: 55,
      display: "flex", justifyContent: "flex-end", animation: "fadeIn 220ms ease both",
    }}>
      <div onClick={(e) => e.stopPropagation()} style={{
        width: 460, maxWidth: "92vw", height: "100%", background: "var(--paper)",
        boxShadow: "-12px 0 40px rgba(0,0,0,.15)", display: "flex", flexDirection: "column",
        animation: "slideInRight 340ms cubic-bezier(.2,.8,.2,1) both",
      }}>
        <div style={{
          display: "flex", justifyContent: "space-between", alignItems: "center",
          padding: "20px 24px", borderBottom: "1px solid var(--hairline)", background: "var(--headerBg)",
        }}>
          <div>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, textTransform: "uppercase",
              letterSpacing: ".08em", color: "var(--inkFaint)" }}>Ask Counterpoint</div>
            <div style={{ fontFamily: "var(--font-serif)", fontSize: 15, color: "var(--ink)" }}>
              {company?.name || ticker}
            </div>
          </div>
          <button onClick={onClose} style={{ border: "none", background: "transparent", fontSize: 22,
            cursor: "pointer", color: "var(--inkSoft)", lineHeight: 1 }}>×</button>
        </div>

        <div ref={scrollRef} style={{ flex: 1, overflowY: "auto", padding: "20px 20px 8px" }}>
          {messages.length === 0 && (
            <div style={{ animation: "fadeIn 400ms ease both" }}>
              <div style={{ fontFamily: "var(--font-serif)", fontSize: 14, color: "var(--inkSoft)",
                marginBottom: 16, lineHeight: 1.6, animation: "slideUpIn 420ms var(--ease-out) both" }}>
                Ask about {company?.name || ticker}'s claims and detected contradictions.
                Answers are grounded in this company's filings, with citations.
              </div>
              {suggestions.length > 0 && (
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {suggestions.map((q, i) => (
                    <button key={q} onClick={() => send(q)}
                      onMouseEnter={(e) => { e.currentTarget.style.borderColor = "var(--accent)"; e.currentTarget.style.background = "var(--accentSoft)"; }}
                      onMouseLeave={(e) => { e.currentTarget.style.borderColor = "var(--hairline)"; e.currentTarget.style.background = "var(--paperCard)"; }}
                      style={{
                        textAlign: "left", border: "1px solid var(--hairline)", borderRadius: 10,
                        background: "var(--paperCard)", padding: "10px 14px", cursor: "pointer",
                        fontFamily: "var(--font-serif)", fontSize: 13.5, color: "var(--ink)",
                        transition: "border-color 150ms ease, background-color 150ms ease, transform 150ms var(--ease-out)",
                        animation: `slideUpIn 400ms var(--ease-out) ${120 + i * 70}ms both`,
                      }}>
                      {q}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          {messages.map((m, i) => (
            <Bubble key={i} role={m.role} text={m.text} ts={m.ts}
              onOpenCitation={onOpenCitation}
              pending={streaming && i === messages.length - 1 && m.role === "assistant"} />
          ))}
          <ToolIndicator tool={activeTool} />
          {!streaming && !error && (
            <FollowupChips questions={followups} onPick={(q) => send(q)} disabled={streaming} />
          )}
          {error && (
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 8,
              animation: "slideUpIn 300ms var(--ease-out) both" }}>
              <span style={{ color: "var(--sev-high)", fontFamily: "var(--font-mono)", fontSize: 12 }}>
                {error}
              </span>
              <button onClick={retry} disabled={streaming} title="Retry" className="cp-press"
                onMouseEnter={(e) => { if (!streaming) e.currentTarget.style.borderColor = "var(--accent)"; }}
                onMouseLeave={(e) => { e.currentTarget.style.borderColor = "var(--hairline)"; }}
                style={{
                  border: "1px solid var(--hairline)", borderRadius: 999, background: "transparent",
                  color: "var(--inkSoft)", fontSize: 13, width: 22, height: 22, lineHeight: 1,
                  cursor: streaming ? "default" : "pointer", padding: 0, flexShrink: 0,
                }}>
                ↻
              </button>
            </div>
          )}
        </div>

        <form onSubmit={(e) => { e.preventDefault(); send(input); }} style={{
          display: "flex", gap: 8, padding: 16, borderTop: "1px solid var(--hairline)",
        }}>
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={ticker ? `Ask about ${ticker}…` : "Open a company first"}
            disabled={!ticker || streaming}
            style={{
              flex: 1, border: "1px solid var(--hairline)", borderRadius: 999, padding: "10px 16px",
              fontFamily: "var(--font-sans)", fontSize: 13.5, background: "var(--paperCard)",
              color: "var(--ink)", outline: "none",
            }}
          />
          <button type="submit" disabled={!ticker || streaming || !input.trim()} style={{
            border: "none", borderRadius: 999, padding: "10px 18px", cursor: "pointer",
            background: "var(--accent)", color: "#fff", fontFamily: "var(--font-mono)",
            fontSize: 12, opacity: !ticker || streaming || !input.trim() ? 0.5 : 1,
          }}>
            Send
          </button>
        </form>
      </div>
    </div>
  );
}
