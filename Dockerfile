# ══════════════════════════════════════════════════════════════════
#  NexAgent — Dockerfile
# ══════════════════════════════════════════════════════════════════
#  Multi-stage build for the LangGraph agent platform.
#  Serves via LangGraph API Server on port 8123.
# ══════════════════════════════════════════════════════════════════

# ── Stage 1: Dependencies ──────────────────────────────────────
FROM python:3.11-slim AS deps

WORKDIR /app

# System deps for building native extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --no-cache-dir . && pip cache purge

# ── Stage 2: Runtime ──────────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

# Copy installed packages from deps stage
COPY --from=deps /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin

# Copy application source
COPY src/ ./src/
COPY langgraph.json ./

ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

EXPOSE 8123

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8123/health')" || exit 1

CMD ["uvicorn", "nexagent.api:app", "--host", "0.0.0.0", "--port", "8123"]
