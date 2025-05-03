# 🎙️ lab12

Offline streaming transcript + one-click AI lecture notes.

---

## Features

- Real-time transcription using Vosk (offline).
- AI-powered note generation using OpenAI API (GPT-4o recommended).
- Editable full transcript.
- Markdown preview for generated notes (powered by Marked.js).
- Session persistence (transcript, notes, custom instructions saved in local storage).
- Custom instructions for AI note generation.
- JWT-based authentication for API endpoints and WebSocket.
- Rate limiting for the AI note generation endpoint.
- **Save generated notes directly to Google Drive** (requires setup).
  - Uses the Google Picker UI to select or create folders.
  - Uploaded as native Google Docs via backend HTML conversion.

---

## Prerequisites

- Python 3.9+ (tested on 3.12)
- PostgreSQL Database (for user authentication/sessions)
- macOS / Linux; Windows works if you install `sounddevice` deps.
- An OpenAI API key (`gpt-4o` tier recommended)
- ~2 GB free disk for Vosk model
- Internet connection (to call OpenAI API and Google Drive API)
- Docker and Docker Compose (Recommended for easy setup)
- Redis (Optional, for persistent rate limiting; defaults to in-memory)
- **Google Cloud Project** with API Key and OAuth 2.0 Client ID for Google Drive integration (see setup below).

## Quick start (Manual Setup)

```bash
# Clone the repository
git clone https://github.com/sibisai/lab12 && cd lab12

# 1. Create & activate a virtual environment
python -m venv venv && source venv/bin/activate
# Or on Windows: venv\Scripts\activate

# 2. Install all Python dependencies
pip install -r requirements.txt

# 3. Download the Vosk model (~1.8 GB)
# Make sure curl and unzip are installed
curl -L -o vosk-model-en-us-0.22.zip \
     https://alphacephei.com/vosk/models/vosk-model-en-us-0.22.zip
unzip vosk-model-en-us-0.22.zip -d models
rm vosk-model-en-us-0.22.zip

# 4. Set up PostgreSQL database and get connection string.

# 5. Create a .env file and provide necessary secrets/config
#    (Copy from .env.example or see .env Example section below)
#    Make sure to fill in your DATABASE_URL, OPENAI_API_KEY, Google keys etc.

# 6. Run the server (ensure PostgreSQL is running)
python -m uvicorn main:app --host 0.0.0.0 --port 8000

# 7. Open the application in your browser
# Then visit http://127.0.0.1:8000/
```

---

## Running with Docker (Recommended)

This method uses Docker and Docker Compose to package the application and its dependencies, including the Vosk model and Redis, into containers for easy setup and consistent execution.

### Prerequisites:

- Docker and Docker Compose installed.
- An OpenAI API key and an initial authentication secret.
- Google Cloud API Key and OAuth 2.0 Client ID (see Google Drive Setup).
- PostgreSQL connection string.

### Setup:

1.  **Clone the repo:**
    ```bash
    git clone https://github.com/sibisai/lab12 && cd lab12
    ```
2.  **Ensure files exist:** `Dockerfile`, `docker-compose.yml`, `requirements.txt`, `main.py`, `index.html`.
3.  **Create `.env` file:** Copy from `.env.example` (if provided) or use the example below. Fill in your actual secrets (OpenAI key, Google keys, `DATABASE_URL`, `INITIAL_AUTH_SECRET`, etc.).
4.  **Build the Docker images:**
    ```bash
    docker compose build
    ```
5.  **Run the services:** (This will start the FastAPI app, Redis, and potentially PostgreSQL if configured in compose)
    ```bash
    docker compose up
    ```
6.  **Access LiveNote:** Navigate to `http://localhost:8000/` (or the port mapped in your `docker-compose.yml`, assuming it maps container port 8000 to host port 8000).

---

## Security Features

### User Registration & Login

- **Registration (`POST /register`):**  
  New users can sign up with a username and password. Passwords are hashed using bcrypt (via Passlib) and stored in PostgreSQL.
- **Login (`POST /token`):**  
  Users submit their credentials (OAuth2 “password” grant). On success, the server issues a JWT (signed with `JWT_SECRET_KEY`, HS256) containing the user’s username as the `sub` claim.

> **Note:** Two‑factor authentication isn’t implemented yet—email/2FA flows are planned for a future release.

### JWT Authentication

- **Mechanism:**  
  All protected endpoints (`/summarize`, `/save-to-drive`, `/feedback`) and the STT WebSocket (`/ws/stt`) require a valid JWT.
- **Access:**
  - **HTTP calls:** JWT is sent in the `Authorization: Bearer <token>` header; validated via a FastAPI dependency (`OAuth2PasswordBearer` → `verify_token`).
  - **WebSocket:** JWT is passed as a `?token=<token>` query parameter; validated by `get_token_for_websocket`.
- **Expiration:**  
  Tokens expire after `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` (default 60 min); expired tokens trigger a 401 and require re‑login.

### Password Security

- **Hashing:** Passwords are hashed with bcrypt (via Passlib’s `CryptContext`).
- **Storage:** User records (username, password_hash, `created_at`, `last_login`) live in PostgreSQL.

### Rate Limiting

- **Mechanism:**  
  The `/summarize` endpoint is rate‑limited with SlowAPI (using the JWT subject as the key).
- **Configurable Rules:**
  - Per‑minute limit: `RATE_LIMIT_SUMMARIZE_MINUTE` (default “5/minute”)
  - Per‑day limit: `RATE_LIMIT_SUMMARIZE_DAY` (default “100/day”)
- **Storage:**
  - In‑memory SlowAPI store (limits reset on server restart; good enough until production traffic).

---

## Google Drive Integration

### Setup (Google Cloud Console)

1.  Create or select a project in the [Google Cloud Console](https://console.cloud.google.com/).
2.  **Enable APIs:** Navigate to "APIs & Services" -> "Library" and enable:
    - Google Drive API
    - Google Picker API
3.  **Create API Key:**
    - Go to "APIs & Services" -> "Credentials".
    - Click "Create Credentials" -> "API key".
    - **Important: Restrict the key.**
      - Under "API restrictions", select "Restrict key" and choose only the "Google Picker API".
      - Under "Application restrictions", select "HTTP referrers (web sites)" and add your application's origin (e.g., `http://localhost:8000`, `http://127.0.0.1:8000`, and your production URL if applicable).
    - Copy the generated API key and add it to your `.env` file as `GOOGLE_API_KEY`.
4.  **Create OAuth 2.0 Client ID:**
    - Go to "APIs & Services" -> "Credentials".
    - Click "Create Credentials" -> "OAuth client ID".
    - If prompted, configure the "OAuth consent screen" first (User Type: External/Internal, App name, User support email, Authorized domains, Developer contact).
    - Select Application type: "Web application".
    - Under "Authorized JavaScript origins", add your application's origin (e.g., `http://localhost:8000`, `http://127.0.0.1:8000`).
    - No "Authorized redirect URIs" are needed for this Picker flow.
    - Click "Create". Copy the generated "Client ID" and add it to your `.env` file as `GOOGLE_CLIENT_ID`.

### Usage

1.  Ensure your `.env` file contains your `GOOGLE_API_KEY` and `GOOGLE_CLIENT_ID`.
2.  Run the application and generate some notes.
3.  Click the “💾 Save to Google Drive” button.
4.  A Google sign-in window will pop up (if not already signed in). Select your account.
5.  Grant the application permission to "See, edit, create, and delete only the specific Google Drive files you use with this app". This is requested by the `https://www.googleapis.com/auth/drive.file` scope.
6.  The Google Picker interface will appear, allowing you to browse your Drive folders. You can select an existing folder or create a new one using the button within the Picker.
7.  Click "Select" on a folder.
8.  The frontend sends the notes, folder ID, and temporary Google access token to the backend `/save-to-drive` endpoint.
9.  The backend converts the Markdown notes to HTML and uploads the file to the selected Drive folder as a native Google Doc.
10. A confirmation message appears upon success.

---

## .env Example

Create a file named `.env` in the project root:

```dotenv
# Required Secrets
OPENAI_API_KEY=sk-proj-...your_openai_api_key...
INITIAL_AUTH_SECRET=replace_with_your_strong_secret_for_initial_login

# Required for Google Drive Integration
GOOGLE_API_KEY=AIzaSy...your_google_api_key...
GOOGLE_CLIENT_ID=1234567890-abc...xyz.apps.googleusercontent.com

# Required for Database connection (adjust as needed)
DATABASE_URL=postgresql+asyncpg://livenote:lab12admin@localhost:5432/livenote

# Optional - JWT Configuration (defaults are often suitable)
# JWT_SECRET_KEY=a_different_strong_secret_for_signing_tokens
# JWT_ALGORITHM=HS256
# JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60

# Optional - Rate Limiting (defaults are often suitable)
# RATE_LIMIT_SUMMARIZE_MINUTE=5/minute
# RATE_LIMIT_SUMMARIZE_DAY=100/day
```

**Note:** Never commit your `.env` file to version control (add it to `.gitignore`).

---

## Folder Layout

```text
LAB12/
├── .env                     # Local secrets (DO NOT COMMIT)
├── .gitignore
├── .dockerignore
├── docker-compose.yml       # Compose entrypoint for app
├── LICENSE.md
├── README.md
├── static/                  # Frontend assets
│   ├── favicon/
│   ├── index.html
│   └── styles.css
├── models/                  # Vosk speech models
│   ├── vosk-model-en-us-0.22/
│   └── vosk-model-small-en-us-…
├── server/                  # All backend code & config
│   ├── __init__.py
│   ├── auth.py
│   ├── crud.py
│   ├── db.py
│   ├── main.py
│   ├── models.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── tests/               # Unit & integration tests
│       ├── test_auth.py
│       └── test_rate_limit.py
└── README.md                # (this file)
```

---

## How It Works

- **Transcription:** Browser captures microphone audio → Sends audio chunks via WebSocket (`/ws/stt?token=<JWT>`) → Backend receives audio → Vosk performs Speech-to-Text → Backend sends partial/final transcript text back via WebSocket → Frontend displays transcript.
- **Note Generation:** User clicks "Generate Notes" → Frontend sends full transcript via POST to `/summarize` (with JWT) → Backend sends text (+ custom instructions) to OpenAI API (GPT-4o) → OpenAI returns Markdown notes → Backend sends Markdown to frontend.
- **Markdown Preview:** Frontend uses Marked.js library to render received Markdown as HTML in the notes preview pane.
- **Google Drive Save:**
  1.  User clicks "Save to Google Drive".
  2.  Frontend uses Google Identity Services to request an OAuth 2.0 access token from Google for the `drive.file` scope (user selects account, grants consent via pop-up).
  3.  Frontend uses Google Picker API (with OAuth token & API key) to display the folder selection UI. User selects or creates a folder.
  4.  Frontend `pickerCallback` receives the selected folder ID.
  5.  Frontend POSTs the markdown notes, filename, folder ID, and Google OAuth token to the backend `/save-to-drive` endpoint (using the app's JWT for backend auth).
  6.  Backend uses the received Google OAuth token to authenticate to Google Drive API.
  7.  Backend converts Markdown notes to HTML.
  8.  Backend uses Google Drive API to create a new file in the specified folder, uploading the HTML content with the Google Docs MIME type (`application/vnd.google-apps.document`) for automatic conversion.
  9.  Backend responds to frontend with success/failure status.

---

## Future Enhancements

- **Robust Rate‑Limiting & Scaling**
  Integrate Redis‑backed rate‑limiting (and test it thoroughly) to enforce quotas per user and protect the OpenAI endpoint under load.

- **Comprehensive Testing Suite**

  - Unit, integration, and regression tests for auth, WebSocket transcription, summarization, and Google Drive saving
  - Docker‑based CI runs to validate container builds and configurations

- **Enhanced Authentication & Security**

  - Full user accounts with secure password hashing (Passlib)
  - Email‑driven 2FA flow (send codes, verify)
  - Token refresh and session management

- **Paid Service / Payment Integration**

  - Stripe (or similar) integration for subscription billing
  - “Freemium” tier limits vs. paid plans
  - Admin dashboard for managing subscribers and usage

- **Speaker Diarization**
  Attempt to identify and tag different speakers in the transcript.

- **Cloud Storage Options**
  Add support for Dropbox, OneDrive, etc., alongside Google Drive.

- **Alternative AI Models**
  Allow swapping between GPT‑4o, local LLMs, or other cloud models for summarization.

- **Real‑time Summarization**
  Explore incremental note generation as the transcript streams in.

- **Improved UI/UX**
  More intuitive controls, responsive design

- **Export Formats**
  Offer additional download options (plain text, PDF, Word `.docx`, etc.).

---

## Testing & Quality

- **Logging:** Application uses Python's standard `logging` module for structured server-side logs.
- **Tests:** Basic tests for authentication and rate limiting are included. Run using `pytest`:

  ```bash
  pytest
  ```

- **CI/CD:** Consider integrating tools like `flake8` (linting), `mypy` (type checking), and `pytest` into a Continuous Integration pipeline (e.g., GitHub Actions) to ensure code quality on each push.

---

## Acknowledgements

This project utilizes several fantastic open-source libraries and services. Many thanks to their creators and maintainers:

- **Vosk:** For offline speech recognition. (Alpha Cephei)
- **OpenAI:** For providing the powerful language models used in note generation. (OpenAI)
- **Google:** For the Google Drive API, Google Picker API, and Google Identity Services used for cloud storage and authentication. (Google Cloud)
- **FastAPI:** For the high-performance web framework. (FastAPI)
- **Uvicorn:** For the ASGI server. (Uvicorn)
- **Marked.js:** For client-side Markdown rendering. (Marked.js)
- **SlowAPI:** For rate limiting API endpoints. (SlowAPI)
- **SQLAlchemy, asyncpg, psycopg2-binary:** For database interaction.
- **python-dotenv:** For managing environment variables.
- **Passlib:** For password hashing.

Enjoy seamless, offline-first transcription and AI-powered note taking with lab12!
