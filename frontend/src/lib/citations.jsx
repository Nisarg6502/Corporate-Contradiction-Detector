const BRACKET_MAP = { "【": "[", "】": "]", "［": "[", "］": "]" };

function normalizeBrackets(text) {
  return (text || "").replace(/[【】［］]/g, (ch) => BRACKET_MAP[ch]);
}

// Matches a bracketed citation span starting with a 16-hex claim id, tolerant
// of trailing annotation text before the closing bracket (mirrors the
// backend's tolerant regex in chatbot/guardrails.py).
const CITATION_SPAN_RE = /\[([0-9a-f]{16})[^\]]*\]/g;

const citeStyle = {
  border: "none", background: "var(--accentSoft)", color: "var(--accent)",
  borderRadius: 5, fontFamily: "var(--font-mono)", fontSize: 10,
  padding: "0 4px", verticalAlign: "super", lineHeight: 1, marginLeft: 1,
};

// Claim ids in order of first appearance, deduped — the single source of
// truth for both the inline marker numbers and the "Source N" chip list, so
// the two can never disagree.
export function extractCitationOrder(text) {
  const normalized = normalizeBrackets(text);
  const order = [];
  const seen = new Set();
  let m;
  CITATION_SPAN_RE.lastIndex = 0;
  while ((m = CITATION_SPAN_RE.exec(normalized))) {
    if (!seen.has(m[1])) { seen.add(m[1]); order.push(m[1]); }
  }
  return order;
}

// Splits a plain text run into string segments and small clickable [N] markers
// in place of the raw bracketed claim id — readers should never see the
// internal hex id inline, only a footnote-style number tied to the source
// chips. `keyPrefix` keeps React keys unique when this is called many times
// across markdown blocks/inline spans.
export function renderCitedInline(text, order, onOpenCitation, keyPrefix = "c") {
  const normalized = normalizeBrackets(text);
  const nodes = [];
  let lastIndex = 0;
  let key = 0;
  CITATION_SPAN_RE.lastIndex = 0;
  let m;
  while ((m = CITATION_SPAN_RE.exec(normalized))) {
    if (m.index > lastIndex) nodes.push(normalized.slice(lastIndex, m.index));
    const id = m[1];
    const idx = order.indexOf(id);
    const label = idx >= 0 ? idx + 1 : "?";
    nodes.push(
      <button
        key={`${keyPrefix}-${key++}`}
        onClick={() => onOpenCitation && onOpenCitation(id)}
        title={id}
        style={{ ...citeStyle, cursor: onOpenCitation ? "pointer" : "default" }}
      >
        {label}
      </button>
    );
    lastIndex = CITATION_SPAN_RE.lastIndex;
  }
  if (lastIndex < normalized.length) nodes.push(normalized.slice(lastIndex));
  return nodes;
}

// Back-compat: plain (non-markdown) cited text. Kept for any caller that wants
// citation handling without markdown block parsing.
export function renderCitedText(text, order, onOpenCitation) {
  return renderCitedInline(text, order, onOpenCitation, "cite");
}
