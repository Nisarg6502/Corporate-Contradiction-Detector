# Counterpoint — single container: FastAPI backend + built React SPA.
# Built by Cloud Build (`gcloud run deploy --source .`); no local Docker needed.

# ---- Stage 1: build the Vite frontend --------------------------------------
FROM node:20-slim AS frontend
WORKDIR /fe
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# Empty API base => the SPA calls the same origin it is served from (Cloud Run).
ENV VITE_API_URL=""
RUN npm run build

# ---- Stage 2: Python backend (serves the API and the built SPA) ------------
FROM python:3.11-slim AS app
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    FASTEMBED_CACHE_DIR=/app/.fastembed_cache

COPY requirements.txt ./
RUN pip install -r requirements.txt

# Bake the FastEmbed ONNX model into the image so cold starts don't download it.
# Uses FASTEMBED_CACHE_DIR (a persistent path) — Cloud Run's /tmp is an empty
# tmpfs at runtime, so the default /tmp cache would otherwise be lost.
# The model is pulled unauthenticated from HuggingFace Hub, which intermittently
# rate-limits and leaves sockets hung; a per-attempt `timeout` + retry loop
# keeps a stalled download from hanging the whole build indefinitely.
ENV HF_HUB_DOWNLOAD_TIMEOUT=30
RUN set -e; ok=0; \
    for i in 1 2 3 4 5; do \
      if timeout 240 python -c "from fastembed import TextEmbedding; list(TextEmbedding(model_name='BAAI/bge-small-en-v1.5', cache_dir='/app/.fastembed_cache').embed(['warmup']))"; then ok=1; break; fi; \
      echo "[warmup] attempt $i failed/timed out; retrying in 10s"; sleep 10; \
    done; \
    if [ "$ok" != "1" ]; then echo "FastEmbed model bake failed after 5 attempts"; exit 1; fi

# Application packages
COPY api/ ./api/
COPY chatbot/ ./chatbot/
COPY config/ ./config/
COPY detection/ ./detection/
COPY extraction/ ./extraction/
COPY graph/ ./graph/
COPY ingestion/ ./ingestion/
COPY observability/ ./observability/
COPY pipeline/ ./pipeline/
COPY vector/ ./vector/
# Demo data: processed claims/documents + synthetic NVDA call PDFs power the
# pre-loaded demo and the citation viewer (read from local files, not the DB).
COPY data/ ./data/
# Built SPA (served same-origin by FastAPI via StaticFiles)
COPY --from=frontend /fe/dist ./frontend/dist

EXPOSE 8080
# Cloud Run injects $PORT; default to 8080 for local runs.
CMD ["sh", "-c", "uvicorn api.app:app --host 0.0.0.0 --port ${PORT:-8080}"]
