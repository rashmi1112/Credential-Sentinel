# Build context: repo root  →  docker build -f backend/Dockerfile .
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Layer: deps (cached unless requirements.txt changes)
COPY backend/requirements.txt .
RUN pip install -r requirements.txt

# Layer: app code
COPY backend/app/ ./app/

# policy.yaml lives at repo root; inside the container BASE_DIR is /app so
# _POLICY_PATH resolves to /policy.yaml (one level above WORKDIR).
COPY policy.yaml /policy.yaml

# SQLite data dir (checkpointer + event log + memory)
VOLUME ["/app/data"]

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
