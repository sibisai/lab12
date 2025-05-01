# 🎙️ LiveNote

Offline streaming transcript + one-click AI lecture notes.

## Features

- Real-time transcription using Vosk (offline).
- AI-powered note generation using OpenAI API (GPT-4o recommended).
- Editable full transcript.
- Markdown preview for generated notes (powered by Marked.js).
- Download notes as PDF directly in-browser (built on html2pdf.js).
- Session persistence (transcript, notes, custom instructions saved in local storage).
- Custom instructions for AI note generation.
- JWT-based authentication for API endpoints and WebSocket.
- Rate limiting for the AI note generation endpoint.
- **(New)** Save generated notes directly to Google Drive (requires setup).
  - Uses the Picker’s `CREATE_NEW_FOLDER` feature on a DocsView (restricted to folders) so users can create new folders in place.
  - Uploaded as native Google Docs via HTML conversion.

## Prerequisites

- Python 3.9+ (tested on 3.12)
- macOS / Linux; Windows works if you install `sounddevice` deps.
- An OpenAI API key (`gpt-4o` tier recommended)
- ~2 GB free disk for Vosk model
- Internet connection (to call OpenAI API and Google Drive API)
- Docker and Docker Compose (Recommended for easy setup)
- Redis (Optional, for persistent rate limiting; defaults to in-memory)
- **(New)** Google Cloud Project with API Key and OAuth 2.0 Client ID for Google Drive integration (see setup below).

## Quick start (Manual Setup)

```bash
git clone https://github.com/sibisai/livenote && cd livenote

# 1. Create & activate a virtual environment
python -m venv venv && source venv/bin/activate

# 2. Install all Python deps (includes Google Drive libs)
pip install -r requirements.txt

# 3. Download the Vosk model (~1.8 GB)
curl -L -o vosk-model-en-us-0.22.zip \\
     https://alphacephei.com/vosk/models/vosk-model-en-us-0.22.zip
unzip vosk-model-en-us-0.22.zip -d models
rm vosk-model-en-us-0.22.zip

# 4. Provide necessary secrets and config in .env
#    (see .env Example section below)

# 5. Run the server and open the demo page
python -m uvicorn backend_gdrive:app --host 0.0.0.0 --port 8082
# Then visit http://127.0.0.1:8082/index.html
```

### Running with Docker (Recommended)

This method uses Docker and Docker Compose to package the application and its dependencies, including the Vosk model, into a container for easy setup and consistent execution.

**Prerequisites:**

- Docker and Docker Compose installed.
- An OpenAI API key and an initial authentication secret.
- **(New)** Google Cloud API Key and OAuth 2.0 Client ID (see Google Drive Setup).

**Setup:**

1. Clone the repo:
   ```bash
   git clone https://github.com/sibisai/livenote && cd livenote
   ```
2. Ensure files exist: `Dockerfile`, `docker-compose.yml`, `requirements.txt`, `backend_gdrive.py`, `index.html`.
3. Create `.env` (see `.env Example` below).
4. Build image:
   ```bash
   docker compose build
   ```
5. Run services:
   ```bash
   docker compose up
   ```
6. Access LiveNote:
   Navigate to http://localhost:8082/index.html (adjust port if needed).

## Security Features

### JWT Authentication

- Mechanism: Endpoints (`/summarize`, `/save-to-drive`) and WebSocket (`/ws/stt`) are protected by JWT.
- Login: Frontend asks for an initial secret (`INITIAL_AUTH_SECRET` in `.env`) to get a JWT.
- Usage: JWT is stored in local storage and sent in `Authorization: Bearer <token>` or as `?token=<token>` for the WebSocket.

### Rate Limiting

- Mechanism: `/summarize` is rate-limited via `slowapi`.
- Defaults: 5 requests/minute, 100/day per user (by JWT subject).
- Backend: Uses Redis if `REDIS_URL` is set; otherwise in-memory.

## Google Drive Integration

### Setup (Google Cloud Console)

1. Create/Select Project in Cloud Console.
2. Enable APIs:
   - Google Drive API
   - Google Picker API
3. Create API Key:
   - Restrict to Google Picker API and your app’s origin.
   - Add to `.env` as `GOOGLE_API_KEY`.
4. Create OAuth 2.0 Client ID:
   - App type: Web application.
   - Authorized origins: e.g. `http://localhost:8082`.
   - Add to `.env` as `GOOGLE_CLIENT_ID`.

### Usage

1. Ensure `.env` has `GOOGLE_API_KEY` and `GOOGLE_CLIENT_ID`.
2. Generate notes, then click “💾 Save to Google Drive.”
3. You’ll be prompted to sign in and grant limited Drive access.
4. Picker lets you select—or create—a folder.
5. The file is uploaded as a Google Doc (HTML → Doc conversion).

## .env Example

```dotenv
# Required
OPENAI_API_KEY=sk-…
INITIAL_AUTH_SECRET=your_secret

# Google Drive Integration
GOOGLE_API_KEY=AIzaSy…your_api_key…
GOOGLE_CLIENT_ID=12345…apps.googleusercontent.com

# Optional - JWT (defaults in code)
# JWT_SECRET_KEY=your_jwt_signing_key
# JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60

# Optional - Rate Limiting
# RATE_LIMIT_SUMMARIZE_MINUTE=5/minute
# RATE_LIMIT_SUMMARIZE_DAY=100/day
# REDIS_URL=redis://localhost:6379
```

## Folder Layout

```
backend_gdrive.py         # Backend with Drive endpoint
index.html                # Frontend with Drive integration
requirements.txt
Dockerfile
docker-compose.yml
.env                       # Secrets (DO NOT commit)
models/
└── vosk-model-en-us-0.22/
tests/
├── test_auth.py
└── test_rate_limit.py
```

## How It Works

1. Browser → `/token` (initial secret) → JWT stored in local storage.
2. Mic → WebSocket (`/ws/stt?token=<JWT>`) → Vosk → live transcript.
3. “📝 Generate Notes” → `/summarize` (with JWT) → GPT-4o → Markdown.
4. Client-side: Markdown preview via Marked.js.
5. PDF: In-browser export via html2pdf.js.
6. Drive:
   - Google Identity Services for OAuth → access token.
   - Google Picker (`CREATE_NEW_FOLDER` feature) → select/create folder.
   - POST to `/save-to-drive` (with JWT + Google OAuth token).
   - Backend converts Markdown → HTML → uploads as Google Doc.

## Testing & Quality

- Logging: Structured via Python’s logging.
- Tests:
  ```bash
  pytest
  ```
- CI: You can integrate linting, type checks, and tests on each push.

---

Enjoy seamless, offline-first transcription and AI-powered note taking with lab12!
