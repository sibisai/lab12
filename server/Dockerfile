# Use an official slim Python image
FROM python:3.10-slim

# Don’t write .pyc files, unbuffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
  PYTHONUNBUFFERED=1

# Install OS packages
RUN apt-get update && apt-get install -y --no-install-recommends \
  curl unzip wkhtmltopdf libatomic1 \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (so mounts below don’t bust your cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download & unpack Vosk model at build time
RUN curl -L -o vosk.zip \
  https://alphacephei.com/vosk/models/vosk-model-en-us-0.22.zip \
  && unzip vosk.zip -d models \
  && rm vosk.zip

# Copy your application code
COPY server/ server/
COPY static/ /app/static/
# (or `COPY . .` if your root only contains app code)

EXPOSE 8000

CMD ["uvicorn", "server.main:app", \
  "--host", "0.0.0.0", "--port", "8000", \
  "--workers", "4", "--proxy-headers"]