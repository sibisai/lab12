# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Prevent Python from writing .pyc files and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
  PYTHONUNBUFFERED=1

# Install system dependencies:
# - curl & unzip for Vosk model download
# - wkhtmltopdf for PDF generation via pdfkit
# - libatomic1 (required by Vosk’s native libvosk.so)
RUN apt-get update && apt-get install -y --no-install-recommends \
  curl \
  unzip \
  wkhtmltopdf \
  libatomic1 \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download & extract the Vosk model (~1.8 GB)
RUN curl -L -o vosk-model-en-us-0.22.zip \
  https://alphacephei.com/vosk/models/vosk-model-en-us-0.22.zip \
  && unzip vosk-model-en-us-0.22.zip -d models \
  && rm vosk-model-en-us-0.22.zip

# Copy the rest of the application code (main.py, static/, etc.)
COPY . .

# Expose the port FastAPI will run on
EXPOSE 8000

# Run the app with Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]