# ==============================================================================
# KargoPilot v6.0 Enterprise Container (Dual Architecture: Cloud & Self-Hosted)
# ==============================================================================

FROM python:3.11-slim-bookworm AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# --- Runtime Stage ---
FROM python:3.11-slim-bookworm AS runtime

LABEL maintainer="Vasif Məcidli <vasif@kargopilot.az>"
LABEL org.opencontainers.image.title="KargoPilot v6.0 Enterprise Logistics & Customs AI"
LABEL org.opencontainers.image.description="Dual-architecture self-hosted & cloud e-commerce, 4-channel health matrix, and SmartCustoms Read-Only quota platform."
LABEL org.opencontainers.image.version="6.0.0"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=48481 \
    HOST=0.0.0.0 \
    APP_DATA_DIR=/data/kargopilot \
    DEPLOYMENT_MODE=sovereign \
    READ_ONLY_SAFE_MODE=true \
    PYTHONPATH=/app/web_panel:/app

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    sqlite3 \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -g 10001 kargopilot \
    && useradd -u 10001 -g kargopilot -m -s /bin/bash kargopilot \
    && mkdir -p /data/kargopilot/invoices /data/kargopilot/logs /data/kargopilot/vault \
    && chown -R kargopilot:kargopilot /data/kargopilot /app

COPY --from=builder /install /usr/local

COPY --chown=kargopilot:kargopilot . /app/

USER kargopilot

EXPOSE 48481

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://127.0.0.1:48481/healthz || exit 1

CMD ["python", "-m", "uvicorn", "web_panel.app.main:app", "--host", "0.0.0.0", "--port", "48481"]
