import { renderCitedInline } from "./citations.jsx";

// Tiny, dependency-free markdown renderer for chat/summary answers. The LLM
// emits light markdown (headings, bullet/numbered lists, **bold**, *italic*,
// `code`) which was previously shown raw. We keep this deliberately small
// instead of pulling in react-markdown + remark (the repo's minimal-deps
// ethos), and — crucially — it composes with the [claim-id] citation markers:
// every plain text run is passed through renderCitedInline so markdown and
// citations render together.

// Inline emphasis: **bold** / *italic* / `code`. Underscore emphasis (_x_,
// __x__) is deliberately NOT supported — LLM prose about filings contains
// snake_case tokens (e.g. topic ids like gross_margin_profitability) that
// underscore-italic would mangle, and models overwhelmingly emit `*` anyway.
// Bold comes first so `**` is consumed before a single `*`.
const INLINE_RE = /(\*\*([^*]+?)\*\*|\*([^*\s][^*]*?)\*|`([^`]+?)`)/g;

function renderInline(text, order, onOpenCitation, keyPrefix) {
  const nodes = [];
  let last = 0;
  let k = 0;
  INLINE_RE.lastIndex = 0;
  let m;
  while ((m = INLINE_RE.exec(text))) {
    if (m.index > last) {
      nodes.push(...renderCitedInline(text.slice(last, m.index), order, onOpenCitation, `${keyPrefix}-t${k}`));
    }
    if (m[2] !== undefined) {
      nodes.push(<strong key={`${keyPrefix}-b${k}`}>{renderCitedInline(m[2], order, onOpenCitation, `${keyPrefix}-bi${k}`)}</strong>);
    } else if (m[3] !== undefined) {
      nodes.push(<em key={`${keyPrefix}-i${k}`}>{renderCitedInline(m[3], order, onOpenCitation, `${keyPrefix}-ii${k}`)}</em>);
    } else if (m[4] !== undefined) {
      nodes.push(
        <code key={`${keyPrefix}-c${k}`} style={{
          fontFamily: "var(--font-mono)", fontSize: "0.86em",
          background: "color-mix(in oklch, var(--ink) 7%, var(--paper))",
          borderRadius: 4, padding: "1px 5px",
        }}>{m[4]}</code>
      );
    }
    last = INLINE_RE.lastIndex;
    k++;
  }
  if (last < text.length) {
    nodes.push(...renderCitedInline(text.slice(last), order, onOpenCitation, `${keyPrefix}-t${k}`));
  }
  return nodes;
}

// Strip a leading "**Heading**" that occupies a whole line into a real heading,
// and detect list / heading blocks. Returns an array of block descriptors.
function toBlocks(text) {
  const lines = (text || "").replace(/\r\n/g, "\n").split("\n");
  const blocks = [];
  let list = null;
  const flush = () => { if (list) { blocks.push(list); list = null; } };

  for (const raw of lines) {
    const line = raw.replace(/\s+$/, "");
    if (!line.trim()) { flush(); blocks.push({ type: "space" }); continue; }

    const h = /^(#{1,4})\s+(.*)$/.exec(line);
    if (h) { flush(); blocks.push({ type: "heading", level: h[1].length, text: h[2] }); continue; }

    // A line that is *entirely one* bold span reads as a heading (common LLM
    // habit). `[^*]+` (not `.+`) so a line with two bold spans — e.g.
    // "**Q1** beat **Q2**" — stays a paragraph instead of becoming a heading.
    const boldHeading = /^\*\*([^*]+)\*\*:?\s*$/.exec(line.trim());
    if (boldHeading) { flush(); blocks.push({ type: "heading", level: 3, text: boldHeading[1] }); continue; }

    const ul = /^\s*[-*•]\s+(.*)$/.exec(line);
    if (ul) {
      if (!list || list.ordered) { flush(); list = { type: "list", ordered: false, items: [] }; }
      list.items.push(ul[1]);
      continue;
    }
    const ol = /^\s*(\d+)[.)]\s+(.*)$/.exec(line);
    if (ol) {
      if (!list || !list.ordered) { flush(); list = { type: "list", ordered: true, items: [] }; }
      list.items.push(ol[2]);
      continue;
    }

    flush();
    blocks.push({ type: "p", text: line });
  }
  flush();
  return blocks;
}

// Renders markdown text (with inline citations) to an array of React block
// elements. Suitable for streaming: re-parses the partial text each token.
export function renderMarkdown(text, order, onOpenCitation) {
  if (!text) return [];
  const blocks = toBlocks(text);
  const out = [];
  let k = 0;

  // Collapse consecutive spacer blocks so we never render a big empty gap.
  for (let bi = 0; bi < blocks.length; bi++) {
    const b = blocks[bi];
    if (b.type === "space") {
      const prev = out[out.length - 1];
      if (prev && prev.key && String(prev.key).startsWith("sp")) continue;
      out.push(<div key={`sp${k++}`} style={{ height: 7 }} />);
    } else if (b.type === "heading") {
      const size = b.level <= 1 ? 17 : b.level === 2 ? 15.5 : 14.5;
      out.push(
        <div key={`h${k++}`} style={{
          fontFamily: "var(--font-serif)", fontWeight: 600, fontSize: size,
          color: "var(--ink)", margin: "6px 0 2px", lineHeight: 1.35,
        }}>{renderInline(b.text, order, onOpenCitation, `h${k}`)}</div>
      );
    } else if (b.type === "list") {
      const Tag = b.ordered ? "ol" : "ul";
      out.push(
        <Tag key={`l${k++}`} style={{
          margin: "4px 0", paddingLeft: 20,
          display: "flex", flexDirection: "column", gap: 4,
        }}>
          {b.items.map((it, i) => (
            <li key={i} style={{ lineHeight: 1.6, paddingLeft: 2 }}>
              {renderInline(it, order, onOpenCitation, `l${k}-${i}`)}
            </li>
          ))}
        </Tag>
      );
    } else {
      out.push(
        <div key={`p${k++}`} style={{ margin: 0, lineHeight: 1.65 }}>
          {renderInline(b.text, order, onOpenCitation, `p${k}`)}
        </div>
      );
    }
  }
  return out;
}
