
"""
Lab12
--------
FastAPI + WebSocket (Vosk) ➜ OpenAI summary ➜ PDF export (FPDF2) ➜ Google Drive Save
Audio: 16 kHz mono 16-bit PCM
"""

import os, json, textwrap, datetime, re, logging # Import logging
from urllib.parse import quote
from dotenv import load_dotenv # Import dotenv
from fastapi import FastAPI, WebSocket, WebSocketException, Response, HTTPException, Depends, status, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from typing import Optional, Annotated
from vosk import Model, KaldiRecognizer
from openai import AsyncOpenAI
import markdown2
from io import BytesIO
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import timedelta
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address, get_ipaddr
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
import redis.asyncio as redis
# Db imports
from contextlib import asynccontextmanager
from server.db import engine, get_db
from sqlalchemy.ext.asyncio import AsyncSession
from server import crud, models
# Google API Imports
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload
# PDF Generation (Using FPDF2 for macOS compatibility)
from fpdf import FPDF, HTMLMixin

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

# ── Rate Limiting Settings ──────────────────────────────────────────────────
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
RATE_LIMIT_SUMMARIZE_MINUTE = os.getenv("RATE_LIMIT_SUMMARIZE_MINUTE", "5/minute")
RATE_LIMIT_SUMMARIZE_DAY = os.getenv("RATE_LIMIT_SUMMARIZE_DAY", "100/day")

# Password hashing context (using bcrypt)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme for dependency injection
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# ── Lifespan: create tables on startup ───────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)
    yield
    # no teardown

# ── Create FastAPI with lifespan ─────────────────────────────────────────
app = FastAPI(lifespan=lifespan)

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

# Dependency to get current user from JWT
async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    return verify_token(token, credentials_exception)

async def get_token_for_websocket(token: Annotated[str | None, Query()] = None):
    if token is None:
        logger.warning("WebSocket connection attempt without token.")
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Missing token")
    credentials_exception = WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token")
    username = verify_token(token, credentials_exception)
    return username

# ── Rate Limiter Setup ──────────────────────────────────────────────────────
# Use the JWT subject (username) as the key for rate limiting
def get_limiter_key(request: Request) -> str:
    try:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            # Use a non-raising exception for key generation context
            username = verify_token(token, JWTError("Invalid token for rate limit key")) 
            return username # Use username from JWT as key
        else:
            logger.debug("No valid Bearer token found in headers for rate limit key, falling back to IP.")
    except JWTError:
        logger.debug("Invalid JWT token for rate limit key, falling back to IP.")
    except Exception as e:
        logger.warning(f"Unexpected error getting rate limit key from token: {e}, falling back to IP.")
        
    ip_addr = get_ipaddr(request)
    logger.debug(f"Using IP address {ip_addr} for rate limit key.")
    return ip_addr

limiter = Limiter(key_func=get_limiter_key)

# ── OpenAI client ───────────────────────────────────────────────────────────
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ── Constants ───────────────────────────────────────────────────────────────
MODEL_PATH  = "models/vosk-model-en-us-0.22"
SAMPLE_RATE = 16_000  # Hz
MAX_CUSTOM_INSTRUCTION_LENGTH = 500 # Max characters for simple custom instructions

# Add Rate Limiter Middleware
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# Add CORS Middleware (ensure it's added correctly relative to other middleware if needed)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

# ── Redis connection on startup ─────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    try:
        redis_conn = redis.from_url(REDIS_URL, encoding="utf-8", decode_responses=True)
        await redis_conn.ping() # Check connection
        limiter.storage = redis_conn
        logger.info(f"Connected to Redis at {REDIS_URL} for rate limiting.")
    except Exception as e:
        logger.error(f"Error connecting to Redis at {REDIS_URL}: {e}")
        # Fallback to in-memory limiter if Redis connection fails
        logger.warning("Falling back to in-memory rate limiter.")
        limiter.storage = None # Or use an in-memory storage explicitly if slowapi provides one

@app.on_event("shutdown")
async def shutdown():
    if hasattr(limiter, 'storage') and limiter.storage: # Check if storage exists
        try:
            await limiter.storage.close()
            logger.info("Redis connection closed.")
        except Exception as e:
            logger.error(f"Error closing Redis connection: {e}")

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
async def register(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: AsyncSession = Depends(get_db),
):
    # check uniqueness
    if await crud.get_user_by_username(db, form_data.username):
        raise HTTPException(status_code=400, detail="Username already taken")

    user = await crud.create_user(db, form_data.username, form_data.password)
    return {"username": user.username, "created_at": user.created_at}


@app.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: AsyncSession = Depends(get_db),
):
    user = await crud.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # update last_login
    user.last_login = datetime.datetime.utcnow()
    await db.commit()

    access_token = create_access_token({"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

# ── WebSocket: streaming STT (Protected) ───────────────────────────────────
@app.websocket("/ws/stt")
async def websocket_stt(ws: WebSocket, token: Annotated[str | None, Query()] = None):
    try:
        username = await get_token_for_websocket(token)
        await ws.accept()
        logger.info(f"WebSocket connection accepted for user: {username}")
    except WebSocketException as e:
        logger.warning(f"WebSocket connection rejected: {e.reason}")
        await ws.close(code=e.code, reason=e.reason)
        return

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
    except WebSocketException as e:
        logger.info(f"WebSocket connection closed for user {username} with code {e.code}: {e.reason}")
    except Exception as e:
        logger.error(f"Unexpected WebSocket error for user {username}: {e}", exc_info=True)
        await ws.close(code=status.WS_1011_INTERNAL_ERROR, reason="Internal server error")
    finally:
        logger.info(f"Closing WebSocket resources for user {username}.")
        # Ensure ws is closed if not already
        try:
            await ws.close(code=status.WS_1000_NORMAL_CLOSURE)
        except RuntimeError: # Already closed
            pass 

# ── /summarize (Protected & Rate Limited) ───────────────────────────────────

class SumReq(BaseModel):
    transcript: str = Field(..., alias="transcript")
    custom_instructions: Optional[str] = Field(None, alias="custom_instructions")

    class Config:
        allow_population_by_field_name = True

class SumResp(BaseModel):
    outline: str
@app.post("/summarize", response_model=SumResp)
@limiter.limit(f"{RATE_LIMIT_SUMMARIZE_MINUTE};{RATE_LIMIT_SUMMARIZE_DAY}")
async def summarize(
    request: Request,
    r: SumReq,
    current_user: Annotated[str, Depends(get_current_user)],
):
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
        return SumResp(outline=md)
    except Exception as e:
        logger.error(f"Error calling OpenAI API for user {current_user}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error calling OpenAI API: {e}")
    
# ── /save-to-drive (Protected) ──────────────────────────────────────────────
class DriveSaveReq(BaseModel):
    notes_content: str
    filename: str
    folder_id: str
    google_access_token: str

class DriveSaveResp(BaseModel):
    file_id: str
    file_name: str
    folder_id: str


def markdown_to_html(md: str) -> str:
  return markdown2.markdown(md, extras=["fenced-code-blocks","tables"])

@app.post("/save-to-drive", response_model=DriveSaveResp)
async def save_to_drive(r: DriveSaveReq, current_user: Annotated[str, Depends(get_current_user)]):
    logger.info(f"Save to Google Drive request received for user: {current_user}, folder: {r.folder_id}")
    
    try:
        # Create credentials object from the access token provided by the frontend
        creds = Credentials(token=r.google_access_token)
        
        # Build the Drive v3 service
        service = build('drive', 'v3', credentials=creds)
        
        html_body = markdown_to_html(r.notes_content)

        # 2) Drive metadata – tell Drive we want a Google Doc
        file_metadata = {
          "name": r.filename.rsplit(".",1)[0],                 # drop .md
          "mimeType": "application/vnd.google-apps.document",  # <-- key!
          "parents": [r.folder_id]
        }

        # 3) media upload – send the html blob, *not* markdown
        media = MediaIoBaseUpload(
          BytesIO(html_body.encode("utf-8")),
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
        logger.error(f"An error occurred saving to Google Drive for user {current_user}: {error}")
        raise HTTPException(status_code=500, detail=f"Google Drive API error: {error}")
    except Exception as e:
        logger.error(f"Unexpected error saving to Google Drive for user {current_user}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")
  
# subclass to get write_html()
class PDF(FPDF, HTMLMixin):
    pass

# ── /download-pdf (Protected) ───────────────────────────────────────────────
class PdfReq(BaseModel):
    markdown_content: str
    filename: str = "notes.pdf"  # Default filename

@app.post("/download-pdf")
async def download_pdf(r: PdfReq, current_user: Annotated[str, Depends(get_current_user)]):
    logger.info(f"PDF download request received for user: {current_user}")
    try:
        # 1) Convert Markdown -> HTML
        html_content = markdown2.markdown(
            r.markdown_content,
            extras=["fenced-code-blocks", "tables"]
        )

        # 2) Build PDF and render HTML
        pdf = PDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()

        # 3) Register a font that supports UTF-8 if available
        font_path = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
        if os.path.exists(font_path):
            pdf.add_font("NotoSansCJK", "", font_path, uni=True)
            pdf.set_font("NotoSansCJK", size=12)
            logger.debug("Using NotoSansCJK font for PDF.")
        else:
            pdf.set_font("Helvetica", size=12)
            logger.warning(
                f"Font not found at {font_path}. Falling back to Helvetica. "
                "Unicode characters may not render correctly."
            )

        # 4) Write HTML (will preserve <h1>, <ul>/<li>, <strong>, <em>, tables, etc.)
        pdf.write_html(html_content)

        # 5) Output as bytes
        raw = pdf.output(dest="S")     # returns a bytearray
        pdf_bytes = bytes(raw)         # immutable bytes for Response

        # 6) Clean up filename
        safe_filename = re.sub(r"[^a-zA-Z0-9_.-]", "_", r.filename)
        if not safe_filename.lower().endswith(".pdf"):
            safe_filename += ".pdf"

        logger.info(f"Successfully generated PDF '{safe_filename}' for user {current_user} using FPDF2.")
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={quote(safe_filename)}"},
        )

    except Exception as e:
        logger.error(f"Error generating PDF for user {current_user} using FPDF2: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error generating PDF: {e}")

# ── /feedback (Protected) ─────────────────────────────────────────────────── ADDED
class FeedbackReq(BaseModel):
    feedback_text: str

@app.post("/feedback")
async def submit_feedback(r: FeedbackReq, current_user: Annotated[str, Depends(get_current_user)]):
    logger.info(f"Feedback received from user '{current_user}': {r.feedback_text}")
    # In a real application, you might save this to a database, send an email, etc.
    return {"message": "Feedback received successfully!"}


app.mount("/", StaticFiles(directory="static", html=True), name="static")

# ── Main entry point (for direct execution) ─────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    logger.info("Starting server with uvicorn...")
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))

