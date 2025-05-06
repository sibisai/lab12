
"""
Lab12
--------
FastAPI + WebSocket (Vosk) ➜ OpenAI summary ➜ Google Drive Save
Audio: 16 kHz mono 16-bit PCM
"""

import os, json, textwrap, datetime, re, logging # Import logging
from dotenv import load_dotenv # Import dotenv
from fastapi import FastAPI, WebSocket, WebSocketException, HTTPException, Depends, status, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi import Cookie, Form
import markdown
from pathlib import Path
from pydantic import BaseModel, Field
from typing import Optional, Annotated
from vosk import Model, KaldiRecognizer
from openai import AsyncOpenAI
import bleach
from io import BytesIO
from jose import JWTError, jwt
from datetime import timedelta
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_ipaddr
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
# Db imports
from contextlib import asynccontextmanager
from server.db import engine, get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, select, func
from server import crud, mailer
from server.crud import (
    DEFAULT_PLANS,   
    get_user_by_username,
    create_password_reset_code,
    confirm_password_reset_code,
    update_user_password
)
import server.mailer as mailer
from sqlalchemy import insert
from server.models import Role, User, UserToken, EmailVerification, UserSubscriptionHistory, user_roles
# Google API Imports
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload
# PDF Generation (Using FPDF2 for macOS compatibility)
# from fpdf import FPDF, HTMLMixin

# ── Logging Configuration ─────────────────────────────────────────────────── 
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# ── Security & JWT Settings ─────────────────────────────────────────────────
# Use environment variables for secrets
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "a-very-strong-secret-key-please-change") # Secret for signing JWTs
JWT_ALGORITHM = "HS256"
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", 60)) # Token validity period
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "https://lab12note.com")

# ── HTML sanitising helpers ────────────────────────────────────────────────
EXTRA_TAGS   = {"h1", "h2", "ul", "ol", "li", "br", "p"}       # bullets & breaks too
ALLOWED_TAGS = bleach.sanitizer.ALLOWED_TAGS.union(EXTRA_TAGS) \
                              .difference({"pre", "code"})

ALLOWED_ATTRS          = bleach.sanitizer.ALLOWED_ATTRIBUTES.copy()
ALLOWED_ATTRS["*"]     = ALLOWED_ATTRS.get("*", []) + ["style"]   # keep inline style rules

# --- one CSS block we’ll prepend to every HTML export -------
STYLE_BLOCK = """
<style>
  body { font-family: Helvetica, Arial, sans-serif; line-height: 1.4; }
  h1   { font-size: 32px; margin: 0 0 24px; }
  h2   { font-size: 20px; margin: 24px 0 12px; }
  ul   { margin: 0 0 12px 28px; padding: 0; }
  li   { margin: 6px 0; }
  strong { font-weight: 600; }
</style>
"""

# ── Rate Limiting Settings ──────────────────────────────────────────────────
RATE_LIMIT_SUMMARIZE_MINUTE = os.getenv("RATE_LIMIT_SUMMARIZE_MINUTE", "5/minute")
RATE_LIMIT_SUMMARIZE_DAY = os.getenv("RATE_LIMIT_SUMMARIZE_DAY", "100/day")

# ── Lifespan: create tables on startup ───────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # async with engine.begin() as conn:
    #     await conn.run_sync(models.Base.metadata.create_all)
    yield

# ── Create FastAPI with lifespan ─────────────────────────────────────────
app = FastAPI(lifespan=lifespan)

# ── Content‑Security‑Policy ────────────────────────────────────────────────
@app.middleware("http")
async def add_csp_header(request: Request, call_next):
    resp = await call_next(request)
    resp.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        # passive content
        "img-src 'self' data:; "
        "font-src 'self' https://fonts.gstatic.com; "
        "style-src 'self' 'unsafe-inline'; "

        # active content
        "script-src 'self' 'unsafe-inline' blob: "
            "https://cdnjs.cloudflare.com "
            "https://cdn.jsdelivr.net "
            "https://accounts.google.com "
            "https://apis.google.com; "

        # workers / worklets (Chrome falls back to script-src but add it for spec compliance)
        "worker-src 'self' blob:; "

        # back‑end calls & WebSockets
        "connect-src 'self' https://accounts.google.com https://www.googleapis.com ws:; "

        # iframes / Google picker
        "frame-src https://accounts.google.com https://picker.googleapis.com https://docs.google.com; "
    )
    return resp


# ── JWT Utility Functions ───────────────────────────────────────────────────
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.datetime.now(datetime.timezone.utc) + expires_delta
    else:
        expire = datetime.datetime.now(datetime.timezone.utc) + timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt

def verify_token(token: str, credentials_exception):
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            logger.warning("JWT token missing 'sub' field.")
            raise credentials_exception
        # Return the username (subject) from the token
        return username
    except JWTError as e:
        logger.warning(f"JWT Error during token verification: {e}")
        raise credentials_exception

async def get_token_for_websocket(token: Annotated[str | None, Query()] = None):
    if token is None:
        logger.warning("WebSocket connection attempt without token.")
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Missing token")
    credentials_exception = WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token")
    username = verify_token(token, credentials_exception)
    return username

# ── Rate Limiter Setup ──────────────────────────────────────────────────────
def get_limiter_key(request: Request) -> str:
    # 1) try the session cookie
    cookie_token = request.cookies.get("access_token")
    if cookie_token:
        try:
            username = verify_token(cookie_token, JWTError("bad"))  # <- returns the sub
            return username
        except JWTError:
            pass           # fall through to IP on bad cookie

    # 2) fallback = client IP (same as before)
    return get_ipaddr(request)

limiter = Limiter(key_func=get_limiter_key)

# ── OpenAI client ───────────────────────────────────────────────────────────
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ── Constants ───────────────────────────────────────────────────────────────
MODEL_PATH  = "models/vosk-model-en-us-0.22"
SAMPLE_RATE = 48_000  # Hz
MAX_CUSTOM_INSTRUCTION_LENGTH = 500 # Max characters for simple custom instructions

# Add Rate Limiter Middleware
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# Add CORS Middleware (ensure it's added correctly relative to other middleware if needed)
# app.add_middleware(
#     CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
# )

app.add_middleware(
    CORSMiddleware,
    allow_origins=[PUBLIC_BASE_URL],   # only your front‑end origin
    allow_credentials=True,            #.enable sending/receiving cookies
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    limiter.storage = None

# ── Load Vosk model once ────────────────────────────────────────────────────
if not os.path.exists(MODEL_PATH):
    logger.error(f"Vosk model not found at {MODEL_PATH}. Please download and place it correctly.")
    model = None
else:
    logger.info(f"Loading Vosk model from {MODEL_PATH}...")
    model = Model(MODEL_PATH)
    logger.info("Vosk model loaded successfully.")

# ── Token Endpoint ──────────────────────────────────────────────────────────
class Token(BaseModel):
    access_token: str
    token_type: str


@app.post("/register", status_code=201)
async def register(                                             # ← rewritten
    username:   str = Form(...),
    password:   str = Form(...),
    full_name:  str | None = Form(...),         # optional (make ... if required)
    db: AsyncSession = Depends(get_db),
):
    logger.info(f"Registration attempt for username: {username}")
    # 1) ensure unique
    if await crud.get_user_by_username(db, username):
        raise HTTPException(status_code=400, detail="This email is already in use.")

    # 2) create the user (unverified)
    user = await crud.create_user(db, username, password, full_name)

    # 3) generate & send verification code
    code = await crud.create_verification_code(db, user.username, user.id)
    await mailer.send_verification_email(
        recipient=user.username,
        code=code,
        public_base_url=PUBLIC_BASE_URL
    )
    logger.info(f"Sent verification PIN to {user.username}: {code}")

    # 4) return the new user (frontend knows to show the “enter PIN” form)
    return {
        "username": user.username,
        "created_at": user.created_at,
        "verification_sent": True
    }


@app.post("/token")
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    user = await crud.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.email_verified:
        raise HTTPException(status_code=403, detail="Please verify your e‑mail first")
    
    # secure_cookie = not os.getenv("DEV_INSECURE")
    access_token = create_access_token({"sub": user.username})
    resp = JSONResponse({"username": user.username})
    resp.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=True,          # ✓ only over HTTPS
        # secure=secure_cookie,
        samesite="lax",
        max_age=JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    return resp

@app.post("/logout")
def logout():
    resp = JSONResponse({"message": "Logged out"})
    resp.delete_cookie("access_token", path="/")
    return resp

async def get_current_user_from_cookie(
    access_token: str | None = Cookie(None),
):
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    # reuse your existing verify_token()
    return verify_token(access_token, credentials_exception)

class MeOut(BaseModel):
    username: str
    full_name: str | None

@app.get("/me")
async def get_current_user_route(current_username: str = Depends(get_current_user_from_cookie),
    db: AsyncSession = Depends(get_db),):
    user = await crud.get_user_by_username(db, current_username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return MeOut(username=user.username, full_name=user.full_name)

PLAN_MAP: dict[str, dict] = {p["name"]: p for p in DEFAULT_PLANS}
FREE_PLAN = PLAN_MAP["free"]

@app.get("/me/quota")
async def quota_api(
    current_user: str = Depends(get_current_user_from_cookie),
    db: AsyncSession  = Depends(get_db)
):
    u = await crud.get_user_by_username(db, current_user)
    if not u:
        raise HTTPException(404, "User not found")

    # did they have an admin row?
    admin_q = (
      select(func.count())
      .select_from(user_roles.join(Role))
      .where(user_roles.c.user_id == u.id, Role.name == "admin")
    )
    admin_count = (await db.execute(admin_q)).scalar_one()
    if admin_count:
        return { "remaining": "∞",
            "plan": {"name": "admin", "quota": "∞"}}

    plan = PLAN_MAP.get(u.subscription_plan, FREE_PLAN)
    return {
      "remaining": plan["quota"] - u.summarize_call_count,
      "plan": plan
    }

# ── WebSocket: streaming STT (Protected) ───────────────────────────────────
@app.websocket("/ws/stt")
async def websocket_stt(ws: WebSocket):
    # accept everyone, but record username if cookie is valid
    await ws.accept()
    cookie_token = ws.cookies.get("access_token")
    try:
        username = verify_token(
            cookie_token,
            WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token")
        )
        logger.info(f"WebSocket connection accepted for user: {username}")
    except Exception:
        username = None
        logger.info("WebSocket connection accepted for anonymous user")

    if not model:
        logger.error("Attempted WebSocket connection but Vosk model is not loaded.")
        await ws.send_json({"error": "Vosk model not loaded on server."})
        await ws.close(code=status.WS_1011_INTERNAL_ERROR, reason="Vosk model unavailable")
        return

    rec = KaldiRecognizer(model, SAMPLE_RATE)
    rec.SetWords(True)
    try:
        while True:
            chunk = await ws.receive_bytes()
            logger.debug(f"🔊 got {len(chunk)}-byte chunk from client")
            if rec.AcceptWaveform(chunk):
              res = json.loads(rec.Result())
              logger.debug(f"final: {res['text'][:50]}")
              # send exactly what the client expects:
              await ws.send_json({ "text": res["text"] })
            else:
              pr = json.loads(rec.PartialResult())
              logger.debug(f"partial: {pr['partial'][:50]}")
              await ws.send_json({ "partial": pr["partial"] })
    except WebSocketException:
        logger.info(f"Client disconnected cleanly (user={username})")
    except Exception as e:
        logger.error(f"Unexpected WebSocket error for user {username}: {e}", exc_info=True)
        await ws.close(code=status.WS_1011_INTERNAL_ERROR, reason="Internal server error")
    finally:
        logger.info(f"Cleaning up resources for user {username}")
        try:
            await ws.close(code=status.WS_1000_NORMAL_CLOSURE)
        except RuntimeError:
            # already closed, ignore
            pass

# ── /summarize (Protected & Rate Limited) ───────────────────────────────────
from server.quota import enforce_quota

class SumReq(BaseModel):
    transcript: str
    custom_instructions: str | None = None

    model_config = {"populate_by_name": True}

class SumResp(BaseModel):
    outline: str

@app.post("/summarize", response_model=SumResp)
@limiter.limit(f"{RATE_LIMIT_SUMMARIZE_MINUTE};{RATE_LIMIT_SUMMARIZE_DAY}", error_message="Rate limit exceeded: max 5 notes/minute, 100 notes/day.")
async def summarize(
    request: Request,
    r: SumReq,
    user: Annotated[User, Depends(enforce_quota)],
    db: AsyncSession = Depends(get_db),
):
    current_user = user.username
    logger.info(f"Summarize request received for user: {current_user}")
    now = datetime.datetime.now().strftime("%B %d, %Y at %I:%M %p")

    text = r.transcript
    instructions = r.custom_instructions or ""
    if instructions and len(instructions) > MAX_CUSTOM_INSTRUCTION_LENGTH:
        logger.warning(f"User {current_user} provided custom instructions exceeding length limit.")
        raise HTTPException(
            status_code=400,
            detail=f"Custom instructions exceed maximum length of {MAX_CUSTOM_INSTRUCTION_LENGTH} characters."
        )

    final_prompt = textwrap.dedent(f"""
        You are an expert lecture note-taker.
        The raw transcript below may contain speech-to-text errors;
        correct obvious spelling/grammar mistakes while keeping meaning.
        Produce **Markdown** with:

        # A top-level title you infer from context (or "Untitled Lecture" if unclear)

        **Date & Time:** {now}

        • A bulleted outline (topic → sub-points)
        • "Key Terms" and "Action Items" sections
        • Preserve equations in LaTeX.

        {f"Additionally, follow these specific instructions: {instructions}" if instructions else ""}

        Transcript:
        \"\"\"{text}\"\"\"
    """)

    try:
        chat = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": final_prompt}],
            temperature=0.3,
            max_tokens=700,
        )
        md = chat.choices[0].message.content.strip()

        # bump counters & log call
        async with AsyncSession(engine) as db:
            user = await crud.get_user_by_username(db, current_user)
            await crud.bump_usage(
                db,
                user_id=user.id,
                transcript_len=len(r.transcript),
                tokens_used=chat.usage.total_tokens if chat.usage else 0
            )

        def fix_flat_lists(md: str) -> str:
            """Turn ‘Key Terms – a – b – c’ into proper bullets."""
            def _repl(m):
                title, body = m.group(1), m.group(2)
                items = [f"- {s.strip()}"    # split on “ - ”
                    for s in re.split(r"\s*-\s+(?!-)", body) if s.strip()]
                return f"**{title}:**\n" + "\n".join(items) + "\n"
            
            return re.sub(r"\*\*(Key Terms|Action Items)\*:?\s*(.+)", _repl, md)
        
        md = fix_flat_lists(md)

        return SumResp(outline=md)
    except Exception as e:
        logger.error(f"Error calling OpenAI API for user {current_user}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error calling OpenAI API: {e}")
    

# ── /save-to-drive (Protected) ──────────────────────────────────────────────
class DriveSaveReq(BaseModel):
    notes_html: str
    filename: str
    folder_id: str
    google_access_token: str

class DriveSaveResp(BaseModel):
    file_id: str
    file_name: str
    folder_id: str

@app.post("/save-to-drive", response_model=DriveSaveResp)
async def save_to_drive(r: DriveSaveReq, current_user: Annotated[str, Depends(get_current_user_from_cookie)]): # Use your cookie dependency
    logger.info(f"Save to Google Drive request received for user: {current_user}, folder: {r.folder_id}")

    try:
        # Create credentials object from the access token provided by the frontend
        creds = Credentials(token=r.google_access_token)
        # ------- persist refresh‑token if present ------------------
        if creds.refresh_token:
            async with AsyncSession(engine) as db:
                user_row = await crud.get_user_by_username(db, current_user)
                await db.execute(
                    insert(UserToken).values(
                        user_id       = user_row.id,
                        provider      = "google",
                        refresh_token = creds.refresh_token,
                        expires_at    = datetime.datetime.now(datetime.timezone.utc)
                                        + datetime.timedelta(days=90)
                    ).on_conflict_do_nothing(
                        index_elements=["user_id", "provider"]
                    )
                )
                await db.commit()
        # -------------------------

        # Configure http_client with timeout if needed
        # http_client = httplib2.Http(timeout=300)
        # service = build('drive', 'v3', credentials=creds, http=http_client)
        # OR use default timeout:
        service = build('drive', 'v3', credentials=creds)


        # *** CHANGE: Use received HTML, skip markdown conversion ***
        # html_body = STYLE_BLOCK + md_to_html(r.notes_content) # Old way
        html_body = STYLE_BLOCK + r.notes_html # New way - Prepend style

        # Still sanitize on backend for safety and consistency
        clean_html = bleach.clean(html_body,
                          tags   = ALLOWED_TAGS.union({"style"}), # Make sure style tag is allowed
                          strip  = True,
                          attributes = ALLOWED_ATTRS)
        logger.info(f"Size of HTML body being uploaded: {len(clean_html.encode('utf-8'))} bytes")


        # 2) Drive metadata – tell Drive we want a Google Doc
        file_metadata = {
          "name": r.filename.rsplit(".",1)[0],                 # drop .md
          "mimeType": "application/vnd.google-apps.document",  # <-- key!
          "parents": [r.folder_id]
        }

        # 3) media upload – send the cleaned html blob
        media = MediaIoBaseUpload(
          BytesIO(clean_html.encode("utf-8")),
          mimetype="text/html",          # importable format
          resumable=True
        )

        file = service.files().create(
          body=file_metadata,
          media_body=media,
          fields="id,name" # Request name as well
        ).execute()

        logger.info(f"File '{file.get('name')}' (ID: {file.get('id')}) created successfully in Drive for user {current_user}.")
        return DriveSaveResp(file_id=file.get("id"), file_name=file.get("name"), folder_id=r.folder_id)

    except HttpError as error:
        logger.error(f"An Google Drive API error occurred for user {current_user}: {error}")
         # Try to parse Google's error message if possible
        detail = f"Google Drive API error: {error.resp.status} {error.reason}"
        try:
            error_content = json.loads(error.content.decode('utf-8'))
            if 'error' in error_content and 'message' in error_content['error']:
                detail = f"Google Drive Error: {error_content['error']['message']}"
        except Exception:
            pass # Ignore parsing errors, use generic message
        raise HTTPException(status_code=error.resp.status if error.resp else 500, detail=detail)

    except Exception as e:
        logger.error(f"Unexpected error saving to Google Drive for user {current_user}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Unexpected error saving to Drive: {e}")
    

# ── /feedback (Protected) ─────────────────────────────────────────────────── ADDED
class FeedbackReq(BaseModel):
    feedback_text: str

@app.post("/feedback", status_code=201)
async def submit_feedback(
    r: FeedbackReq,
    current_user: Annotated[str, Depends(get_current_user_from_cookie)],
    db: AsyncSession = Depends(get_db),
):
    await crud.store_feedback(db, (await crud.get_user_by_username(db, current_user)).id, {"text": r.feedback_text})
    try:
        await mailer.send_feedback_alert(r.feedback_text, current_user)
    except Exception as e:
        logger.error("feedback alert mail failed", exc_info=True)
    return {"message": "Thanks for your feedback!"}

class EmailReq(BaseModel): email: str
class PinReq(BaseModel):  email: str; pin: str

# send code ----------------------------------------------------

@app.post("/email/verify/send", summary="Resend a verification code")
async def resend_code(
    r: EmailReq,
    db: AsyncSession = Depends(get_db),
):
    user = await crud.get_user_by_username(db, r.email)
    if not user:
        raise HTTPException(404, "User not found")

    if user.email_verified:
        return {"detail": "Already verified"}

    code = await crud.create_verification_code(db, r.email, user.id)
    await mailer.send_verification_email(r.email, code, PUBLIC_BASE_URL)
    return {"detail": "Verification code resent"}



@app.post("/email/verify/cancel", summary="Cancel a pending signup")
async def cancel_verification(
    r: EmailReq,
    db: AsyncSession = Depends(get_db),
):
    # 1) Look up the user
    user = await get_user_by_username(db, r.email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 2) Blow away any outstanding verification codes
    await db.execute(
        delete(EmailVerification)
        .where(EmailVerification.user_id == user.id)
    )

    # 3) (Optionally) wipe out any other related rows you created at signup
    await db.execute(
        delete(UserSubscriptionHistory)
        .where(UserSubscriptionHistory.user_id == user.id)
    )
    await db.execute(
        delete(user_roles)
        .where(user_roles.c.user_id == user.id)
    )

    # 4) Finally delete the user row itself
    await db.execute(
        delete(User)
        .where(User.id == user.id)
    )

    await db.commit()
    return {"detail": "Signup canceled; you may sign up again"}

VERIFY_OK   = "<h1>Email verified ✅</h1><p>You can close this tab.</p>"
VERIFY_FAIL = "<h1>Invalid or expired link ❌</h1>"

@app.get("/verify", response_class=HTMLResponse)
async def verify_via_link(email: str, pin: str, db: AsyncSession = Depends(get_db)):
    ok = await crud.confirm_code(db, email, pin)
    if ok:
        try:
            user = await crud.get_user_by_username(db, email)
            total = await crud.count_verified_users(db)
            await mailer.send_user_verified_alert(email, user.full_name, total)
        except Exception:
            logger.exception("Failed to send admin alert for email‑link verification")
        return VERIFY_OK
    return VERIFY_FAIL

@app.post("/email/verify/check", summary="Verify a PIN code")
async def check_pin(r: PinReq, db=Depends(get_db)):
    if not await crud.confirm_code(db, r.email, r.pin):
        raise HTTPException(400, "Invalid or expired code")
    
    # send admin alert
    try:
        user = await crud.get_user_by_username(db, r.email)
        total = await crud.count_verified_users(db)
        await mailer.send_user_verified_alert(r.email, user.full_name, total)
    except Exception:
        logger.exception("Failed to send admin alert for PIN verification")

    return {"detail": "verified"}

class ResetConfirmReq(BaseModel):
    email: str
    code: str
    new_password: str

@app.post("/auth/password-reset/request", status_code=202)
async def password_reset_request(r: EmailReq, db: AsyncSession = Depends(get_db)):
    user = await get_user_by_username(db, r.email)
    if user:
        code = await create_password_reset_code(db, r.email, user.id)
        await mailer.send_password_reset_email(r.email, code)

    # always succeed
    return {"detail":"If that email exists, a code has been sent."}

@app.post("/auth/password-reset/verify", status_code=200)
async def password_reset_verify(r: ResetConfirmReq, db: AsyncSession = Depends(get_db)):
    uid = await confirm_password_reset_code(db, r.email, r.code)
    if not uid:
        raise HTTPException(400, "Invalid or expired code")
    await update_user_password(db, uid, r.new_password)
    return {"detail":"Password has been reset."}

# Front end:

app.mount("/static", StaticFiles(directory="static"), name="static")
# 2) tell FastAPI where your templates live
templates = Jinja2Templates(directory="templates")

BASE_DIR = Path(__file__).parent.parent   # one level up from server/
DOCS_DIR = BASE_DIR / "docs"

def render_markdown(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    # you can also use `marked.js` on the client, but here we do it server‑side
    return markdown.markdown(text, extensions=["fenced_code", "tables"])

# ender index.html through Jinja so your partials can be included
@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# same for docs
@app.get("/docs-page", response_class=HTMLResponse)
async def get_docs(request: Request):
    return templates.TemplateResponse("docs.html", {"request": request})

@app.get("/privacy", response_class=HTMLResponse)
async def privacy(request: Request):
    md_path = DOCS_DIR / "PRIVACY.md"
    try:
        html = render_markdown(md_path)
    except FileNotFoundError:
        raise HTTPException(404, "Privacy Policy not found")
    return templates.TemplateResponse("docs.html", {
        "request": request,
        "markdown_content": html,
        "page_title": "Privacy Policy"
    })

@app.get("/terms", response_class=HTMLResponse)
async def terms(request: Request):
    md_path = DOCS_DIR / "TERMS.md"
    try:
        html = render_markdown(md_path)
    except FileNotFoundError:
        raise HTTPException(404, "Terms of Service not found")
    return templates.TemplateResponse("docs.html", {
        "request": request,
        "markdown_content": html,
        "page_title": "Terms of Service"
    })

# ── Main entry point (for direct execution) ─────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    logger.info("Starting server with uvicorn...")
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
