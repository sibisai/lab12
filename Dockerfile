# ─── builder stage ───────────────────────────────────────────────────
FROM python:3.10-slim as builder
WORKDIR /app

# Install only production deps
COPY server/requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Copy your application code
COPY server/     server/
COPY static/     static/

# ─── final stage ─────────────────────────────────────────────────────
FROM python:3.10-slim
WORKDIR /app

# Install runtime deps (including libatomic for Vosk)
RUN apt-get update \
  && apt-get install -y --no-install-recommends libatomic1 \
  && rm -rf /var/lib/apt/lists/*

# Pull in just the pip‑installed packages and code
COPY --from=builder /root/.local    /root/.local
COPY --from=builder /app/server     /app/server
COPY --from=builder /app/static     /app/static

# ─── include the Vosk model ───────────────────────────────────────────
# Assumes you have the model in ./models/vosk-model-en-us-0.22 next to your Dockerfile
COPY models/vosk-model-en-us-0.22 /app/models/vosk-model-en-us-0.22

ENV PATH=/root/.local/bin:$PATH
# **POINT urllib at Certifi’s CA bundle**
# adjust the path if your python version is different
ENV PATH=/root/.local/bin:$PATH \
  SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt

EXPOSE 8000
CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"]