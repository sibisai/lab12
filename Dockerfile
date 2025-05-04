# ─── builder stage ───────────────────────────────────────────────────
FROM python:3.10-slim as builder
WORKDIR /app

COPY server/requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

COPY server/     server/
COPY static/     static/

# ─── final stage ─────────────────────────────────────────────────────
FROM python:3.10-slim
WORKDIR /app

# install runtime deps (including libatomic for vosk)
RUN apt-get update && \
  apt-get install -y --no-install-recommends libatomic1 && \
  rm -rf /var/lib/apt/lists/*

# pull in just the pip‐installed packages and code from builder
COPY --from=builder /root/.local    /root/.local
COPY --from=builder /app/server     /app/server
COPY --from=builder /app/static     /app/static

ENV PATH=/root/.local/bin:$PATH

EXPOSE 8000
CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"]