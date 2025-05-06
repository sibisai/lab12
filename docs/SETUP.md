# Setup for Lab12

## Prerequisites

- Python 3.9+ (tested on 3.12)
- PostgreSQL (for user authentication/sessions)
- macOS/Linux; Windows works if you install `sounddevice` deps
- OpenAI API key (`gpt-4o` tier recommended)
- ~2 GB free disk for Vosk model
- Internet connection (for OpenAI & Google Drive APIs)
- Docker & Docker Compose (recommended)
- Google Cloud project with Drive API & OAuth 2.0 Client ID

---

## Manual Setup

```bash
# 1. Clone the repository
git clone https://github.com/sibisai/lab12 && cd lab12

# 2. Create & activate a virtual environment
python -m venv venv && source venv/bin/activate
# On Windows: venv\\Scripts\\activate

# 3. Install Python dependencies
pip install -r server.requirements.txt

# 4. Download the Vosk model (~1.8 GB)
curl -L -o vosk-model-en-us-0.22.zip \\
     https://alphacephei.com/vosk/models/vosk-model-en-us-0.22.zip
unzip vosk-model-en-us-0.22.zip -d models
rm vosk-model-en-us-0.22.zip

# 5. Set up PostgreSQL and note your connection string

# 6. Configure environment variables (see example below)

# 7. Run the server
uvicorn server.main:app --reload --env-file .env

# 8. Open http://127.0.0.1:8000/ in your browser
```

---

## Docker Setup (Recommended)

```bash
# Build the Docker image
docker build -t lab12:latest .

# Run the container
docker run -d --name lab12-app -p 8000:8000 --env-file .env lab12:latest

# View logs
docker logs -f lab12-app
```

Access the app at http://localhost:8000/.

---

## Security Features

- **Registration** (`POST /register`): Bcrypt‑hashed passwords stored in PostgreSQL
- **Login** (`POST /token`): Issues JWTs (HS256, `JWT_SECRET_KEY`)
- **Protected Endpoints**: `/summarize`, `/save-to-drive`, `/feedback`, and `/ws/stt` require valid JWT
- **Rate Limiting**: SlowAPI enforces per‑minute and per‑day quotas
- **Transport Security**: HTTPS/TLS for all network communication

---

## Google Drive Integration

1. Create or select a project in Google Cloud Console
2. Enable **Google Drive API** & **Google Picker API**
3. Create an **API Key** (restrict to Picker API & your app’s origin)
4. Create an **OAuth 2.0 Client ID** (Web app, add your origins)
5. Add `GOOGLE_API_KEY` & `GOOGLE_CLIENT_ID` to `.env`
6. Run the app and click “💾 Save to Google Drive”
7. Follow the OAuth consent, pick a folder, and upload

---

## Environment Variables

Copy to `.env` and fill in:

```dotenv
OPENAI_API_KEY=sk-...
SENDGRID_API_KEY=SG-...

# JWT (optional overrides)
# JWT_SECRET_KEY=...
# JWT_ALGORITHM=HS256
# JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60

GOOGLE_API_KEY=AIzaSy...
GOOGLE_CLIENT_ID=...

# Database URLs
# Local Postgres dev:
# DATABASE_URL=postgresql+asyncpg://<user>:<pass>@localhost:5432/<dbname>

# Docker dev:
# DATABASE_URL=postgresql+asyncpg://<user>:<pass>@host.docker.internal:5432/<dbname>

EMAIL_SENDER=o-reply@yourdomain.com

# For feedback/logs
ADMIN_EMAIL=admin@yourdomain.com
# For email verification & forgot password emails link
PUBLIC_BASE_URL=https://your-public-domain.com
```

Never commit `.env` to source control (add to `.gitignore`).

---

## Folder Layout

```text
lab12/
├── alembic/                  # Alembic migrations
├── docs/                     # Project docs
│   ├── CODE_OF_CONDUCT.md
│   ├── CONTRIBUTING.md
│   ├── COPYING.AGPL-3.0
│   ├── PRIVACY.md
│   └── SETUP.md
├── models/                   # Vosk speech models
│   └── vosk-model-...
├── server/                   # Backend code
│   ├── __pycache__/
│   ├── __init__.py
│   ├── crud.py
│   ├── db.py
│   ├── grant_admin.py
│   ├── mailer.py
│   ├── main.py
│   ├── models.py
│   ├── quota.py
│   ├── requirements.txt
│   └── seed.py
├── static/                   # Frontend assets
│   ├── favicon/
│   ├── index.html
│   └── styles.css
├── venv/                     # Local virtual environment (ignored)
├── .dockerignore
├── .env                      # Environment variables (ignored)
├── .gitignore
├── alembic.ini
├── docker-compose.yml
├── Dockerfile
├── LICENSE.md
└── README.md
```

---

## Acknowledgements

Thanks to all the libraries & services that power Lab12:

- **Vosk** (offline speech‑to‑text engine, [Apache License 2.0](https://github.com/alphacep/vosk-api/tree/master?tab=Apache-2.0-1-ov-file#readme))
- **OpenAI** (GPT‑4o)
- **Google Drive & Picker APIs**
- **FastAPI**, **Uvicorn**
- **Marked.js**, **SlowAPI**
- **SQLAlchemy**, **asyncpg**
- **SendGrid**, **Passlib**
