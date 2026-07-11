# Demo script — Counterpoint

A fixed, rehearsed path. ~5–7 minutes. NVDA is the showcase (it has planted
contradictions); the other companies show live processing.

## 0. Pre-flight (before the audience arrives)
- Start the backend: `.venv/Scripts/uvicorn api.app:app --port 8000`
- Start the frontend: `npm run dev --prefix frontend` → open http://localhost:5173
- Confirm NVDA, AMD, COST show as **Ready** on the landing page.
- (Optional) Open your Langfuse project in another tab for the observability beat.

## 1. The hook — landing (30s)
- "Companies say a lot across filings and earnings calls. Counterpoint reads all of
  it, builds a graph of every claim, and flags where the story stopped adding up."
- Point out the search + **Popular** / **Recently filed** lists, and that **NVDA is
  Ready** while others say **Process →** (processed live on demand).
- Click **NVDA · NVIDIA CORP (Ready)**.

## 2. The claim timeline (45s)
- Left sidebar = the 9 curated **topics**. Note the **red dots** on *Gross margin*,
  *Regulatory / legal risk*, and *Geographic / customer concentration* — topics with a
  detected contradiction.
- Click **Gross margin / profitability**. Scroll the timeline: point out the **dashed
  "earnings_call · synthetic"** cards vs solid **10-K** filing cards, each with a
  speaker (Jensen Huang / Colette Kress / Company).

## 3. The graph (45s)
- Click **View graph**. Read the "HOW TO READ" line.
- Hover a **node** → the inspector shows that claim + "click to view source".
- Hover the **red edge** → "Contradiction · high severity · click to compare".
- "Solid = real filing, dashed = synthetic call; the red line is a contradiction,
  thicker = higher severity."

## 4. The payoff — a contradiction (60s)
- Click a **"Contradiction · high"** badge (or the red edge). The **compare modal**
  shows the two claims side by side:
  - Kress (Q1 FY2026, earnings call): *"we expect gross margins to continue climbing
    through the remainder of the fiscal year."*
  - Company (FY2026 10-K): *"Gross margin decreased in fiscal year 2026…"*
  - Read the **judgment reasoning** — this is the LLM explaining why they conflict.

## 5. The trust — citations (60s)
- Close the modal, click **View source →** on the **real 10-K** claim: the **book-page**
  citation renders the MD&A paragraph with the exact quote highlighted
  (*"$4.5 billion charge associated with H20 excess inventory"*) and
  **"Quote-span verified exact match."**
- Click **View source →** on a **synthetic** claim: it renders as a **lined PDF page**
  with the quote highlighted and "Rendered from PDF · page 1."
- "Every claim carries a verbatim quote-span — no paraphrase, no hallucinated quotes."

## 6. The other two planted contradictions (30s, optional)
- Sidebar → **Regulatory / legal risk**: Huang's *"no material impact"* vs the real
  export-control charge / 25% tariff / 15% revenue-share disclosures (3 edges).
- Sidebar → **Geographic / customer concentration**: Huang's *"no meaningful
  concentration"* vs the 10-K's *"limited number of partners… concentration of sales."*

## 7. Semantic search (20s)
- Top-right **"Search claims…"**: type *"how did profit margins change?"* → ranked
  claims with ⚠ contradiction flags. Click one to jump to it.

## 8. Live processing — any company (60s)
- Header **New search** → search a company you haven't processed (e.g. **AAPL**) →
  click it. The **processing screen** runs the full pipeline live (Fetching → Extracting
  → Graph → Indexing → Detecting) and drops you into its workspace.
- "This is the same pipeline, run on demand from real SEC filings. Real companies may
  have few or no self-contradictions — that's honest; **COST** shows that case."

## 9. How it works + observability (45s)
- Header **How it works** → the architecture diagram + live stats.
- Switch to the **Langfuse** tab → show the trace tree for a processing run: every
  extraction and judgment LLM call, with latency, tokens, and prompts/outputs.

## Honest framing (say this)
- **SEC filings are real.** The NVDA **earnings-call excerpts are synthetic**, clearly
  tagged, and deliberately seeded with 3 contradictions to demonstrate detection.
- Other companies (AMD, COST, anything processed live) use **only real filings**, so
  their contradictions — if any — are genuine cross-time inconsistencies.
