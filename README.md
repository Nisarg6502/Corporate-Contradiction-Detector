# Counterpoint — Corporate Contradiction Detector

![License: MIT](https://img.shields.io/badge/license-MIT-blue)
![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)
![React + Vite](https://img.shields.io/badge/react-vite-61DAFB?logo=react&logoColor=white)
![Neo4j](https://img.shields.io/badge/graph-Neo4j-008CC1?logo=neo4j&logoColor=white)
![Qdrant](https://img.shields.io/badge/vectors-Qdrant-DC244C)
![tests](https://img.shields.io/badge/tests-63%20passing-3f7d54)

Ingests a company's public SEC filings (10-K / 10-Q / 8-K), extracts every factual
and strategic claim made by named speakers, builds a knowledge graph of those claims,
detects **contradictions across time** (graph traversal + LLM judgment), and surfaces
them through a searchable UI where **every claim traces back to a verbatim quote in its
source document**.

> **Data honesty.** SEC filings are **real**. For the NVIDIA demo, the earnings-call
> excerpts are **synthetic** — clearly tagged everywhere, and deliberately seeded with a
> few planted contradictions to demonstrate detection. Any company processed live uses
> **only real filings**, so its contradictions (if any) are genuine.

---

## What it does

- **Search & process any public company.** Search the full SEC universe; NVDA is
  pre-loaded, any other company is processed **live on demand** (ingest → extract →
  graph → index → detect) with a staged progress screen.
- **Claim timeline** per topic, with real vs synthetic clearly distinguished.
- **Contradiction graph** — an interactive hub-and-spoke view; contradiction edges are
  colored/weighted by severity.
- **Book-page citations** — real filings render as styled HTML with the exact quote
  highlighted inline; synthetic docs render as the actual PDF page with a highlight.
- **Hybrid search** — semantic claim search (Qdrant) enriched with graph context.
- **Ask Counterpoint** — a grounded chat assistant (LangGraph orchestrator + tools)
  scoped to the currently-open company. Every assertion cites a retrieved claim;
  off-topic questions, other-company questions, investment advice, and prompt
  injection are all refused by layered guardrails. Answers stream token-by-token
  (SSE), with suggested-question chips to start the conversation.
- **Executive summary** — a one-click, streamed narrative of a company's key
  topics and detected contradictions, with the same inline citations as chat.
- **Shareable citation card** — a printable/exportable card for a contradiction's
  two verbatim quotes, reachable from the compare view.
- **Full observability** — every extraction/judgment/chat LLM call is traced in Langfuse.

## Screenshots

> Drop PNGs into `docs/screenshots/` with these names and they'll render here. The best
> shots: the landing page, the NVDA gross-margin contradiction (compare modal), the
> contradiction graph, and a book-page citation.

| Landing & discovery | Contradiction compare |
| --- | --- |
| ![Landing](docs/screenshots/landing.png) | ![Compare](docs/screenshots/compare.png) |

| Contradiction graph | Book-page citation |
| --- | --- |
| ![Graph](docs/screenshots/graph.png) | ![Citation](docs/screenshots/citation.png) |

## Architecture

```
EDGAR filings (real) ┐
                     ├─▶ parse ─▶ extract claims ─▶ Neo4j graph ┐
synthetic PDFs ──────┘  (BS4 /    (LLM + verbatim   + Qdrant     ├─▶ detect ─▶ FastAPI ─▶ React UI
                        PyMuPDF)   quote guardrail)   vectors    ┘  (graph +    (citations,
                                                                     LLM judge)   graph, search)
```

| Layer | Tech |
| ----- | ---- |
| Backend | Python, FastAPI |
| Graph DB | **Neo4j Aura** (cloud; Desktop also works) |
| Vector DB | **Qdrant Cloud** (self-host also works) |
| Embeddings | **FastEmbed** (ONNX, CPU, no torch) |
| LLM | **Ollama Cloud `gpt-oss:120b`** for extraction + judgment + chat orchestration/synthesis, **`gpt-oss:20b`** for the fast chat guardrail (config-driven; a Gemini/Vertex path is included) |
| Chat | **LangGraph** supervisor-orchestrator graph (`chatbot/`), streamed over SSE |
| Parsing | `edgartools` + BeautifulSoup (EDGAR HTML), PyMuPDF (synthetic PDFs) |
| Frontend | React + Vite (custom SVG graph + citation viewer) |
| Observability | **Langfuse Cloud** |

Model IDs, the topic list, DB connections, and processing bounds all live in
[`config/`](config/) and are **never hardcoded** in pipeline code.

### Graph data model (Neo4j)

```
(Speaker)-[:MADE]->(Claim)-[:APPEARS_IN]->(Document)-[:FILED_BY]->(Company)
(Claim)-[:ABOUT]->(Topic)
(Claim)-[:CONTRADICTS {severity, reasoning, judged_at}]->(Claim)
```

Every `Claim` carries a `quote_span` (verified verbatim), a `position_anchor`
(document#section#paragraph), and — for synthetic PDFs — `page`/`bbox` for highlighting.

---

## Setup

### Prerequisites
- **Python 3.11+**, **Node 18+**
- Free cloud accounts: **Neo4j Aura**, **Qdrant Cloud**, **Ollama Cloud**; optional
  **Langfuse Cloud** (tracing) and **Google Vertex AI** (alternate LLM).

### 1. Python env + deps
```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1   | macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Environment
```bash
cp .env.example .env      # then fill in — see .env.example for every key
```
Required: `EDGAR_IDENTITY` (name + email for SEC), `OLLAMA_HOST`/`OLLAMA_API_KEY`,
`NEO4J_URI`/`NEO4J_USER`/`NEO4J_PASSWORD`/`NEO4J_DATABASE`, `QDRANT_URL`/`QDRANT_API_KEY`.
Optional: `LANGFUSE_*` (tracing is a no-op without them).

> Aura note: some instances use the **instance id** as both username and database name
> (e.g. `NEO4J_USER=38bcb6ce`, `NEO4J_DATABASE=38bcb6ce`) rather than `neo4j`.

### 3. Frontend deps
```bash
npm install --prefix frontend
```

---

## Running

### Backend API + frontend
```bash
.venv/Scripts/uvicorn api.app:app --port 8000     # API  -> http://localhost:8000/docs
npm run dev --prefix frontend                      # UI   -> http://localhost:5173
```

Open the UI, search a company, and go. See [DEMO.md](DEMO.md) for the rehearsed path.

### Bootstrapping the NVDA demo data (offline pipeline)
The pre-loaded NVDA corpus (with synthetic transcripts + planted contradictions) is built
by the CLI pipeline. To rebuild it from scratch:
```bash
python -m ingestion.run_ingest                                  # fetch + parse NVDA filings
python -m ingestion.run_synthetic                               # generate + parse synthetic PDFs
python -m extraction.run_extract                                # extract claims (LLM + guardrail)
python -m extraction.run_extract --contains "Gross margin decreased" \
                                 --contains "limited number of partners"   # demo anchors
python -m graph.run_load --reset                                # load the graph
python -m vector.run_index                                      # index for search
python -m detection.run_detect                                  # detect contradictions
python -m ingestion.company_universe                            # (optional) refresh recent-filers cache
```

### Live processing (any company)
Selecting an unprocessed company in the UI runs the same pipeline via a background job with
a live progress screen. **A run takes ~3–5 minutes** (measured ~4 min end-to-end for a
mid-cap: ~35s fetching, ~2 min extraction, ~1 min graph/index/detect) on the Ollama free
tier — roughly a coffee run. Bounds are in
[`config/processing.yaml`](config/processing.yaml) (default: 1×10-K + 2×10-Q, 10 chunks/doc,
15 detection pairs); raise them for deeper coverage at the cost of time.

---

## API (selected endpoints)

| Endpoint | Purpose |
| --- | --- |
| `GET /companies` | Processed companies |
| `GET /company-search?q=` · `/popular` · `/recent` | SEC company discovery |
| `POST /companies/{ticker}/process` → `GET /jobs/{id}` | Start + poll a live processing job |
| `GET /companies/{ticker}/topics` | Topics with claim counts |
| `GET /topics/{id}/claims?ticker=` | Claim timeline for a topic |
| `GET /contradictions?ticker=&min_severity=` | Confirmed contradictions |
| `GET /claims/{id}/citation` · `/page.png` | Source citation (HTML data or PDF page) |
| `GET /search?q=&ticker=` | Hybrid semantic + graph search |
| `POST /companies/{ticker}/chat` | Ask Counterpoint — SSE stream of a grounded chat turn |
| `GET /companies/{ticker}/chat/suggestions` | Starter questions for the open company |
| `GET /companies/{ticker}/summary` | SSE stream of a grounded executive summary |

Full interactive docs at `/docs`.

## Observability

With `LANGFUSE_*` set, every extraction (`extract-claims`) and judgment
(`judge-contradiction`) call is a Langfuse **generation** — model, prompt, output,
latency, token usage — grouped under one **trace per pipeline run**. Without keys it's a
silent no-op. Wiring lives in [`observability/`](observability/) and wraps
`extraction/providers.py` + `detection/judge.py`.

## Project structure

```
ingestion/     EDGAR fetch + HTML/PDF parsing; synthetic transcripts; company universe
extraction/    LLM claim extraction + quote-span guardrail (provider-agnostic)
graph/         Neo4j schema, loaders, queries
detection/     candidate-pair Cypher + LLM contradiction judgment
vector/        FastEmbed + Qdrant hybrid search
pipeline/      on-demand company-processing orchestrator
observability/ Langfuse tracing (no-op fallback)
chatbot/       LangGraph chat agent — tools, guardrails, orchestrator/synthesis graph
api/           FastAPI app + background job registry + citation builder + chat router
frontend/      React + Vite app (Counterpoint)
config/        topics, model/provider config, DB connections, processing bounds, chat guardrails
tests/         63 tests (config, ingestion, extraction, graph, detection, api, processing, chatbot)
```

## Testing
```bash
.venv/Scripts/python -m pytest tests/ -q      # 63 tests, network-free
```

## Honest notes & limitations
- **Curated topic list (9 topics), not open-ended.** Deliberate for a clean, controlled v1.
- **Synthetic data is NVDA-only** and clearly tagged; it exists to demonstrate detection.
  Live-processed companies are real-filings-only and may show few/zero contradictions.
- **Cost/latency.** Live processing is bounded to keep runs to a few minutes on free tiers;
  raise `config/processing.yaml` bounds for deeper coverage.
- **The quote-span guardrail is a hard constraint** — the entire citation feature and the
  project's credibility depend on it; claims that fail verbatim validation are dropped.

## License

[MIT](LICENSE) © Nisarg Kudgunti
