"""
Reusable async helpers for Lab12 e‑mail.

send_verification_email()  – 6‑digit PIN, HTML+plain, deep‑link button  
send_feedback_alert()      – sends moderators a copy of user feedback
"""
import os, ssl, smtplib, certifi, secrets, asyncio
from email.message import EmailMessage
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv, find_dotenv
import bleach
import traceback

# ── env ────────────────────────────────────────────────────────────────────
load_dotenv(find_dotenv(), override=True)

EMAIL_SENDER   = os.getenv("EMAIL_SENDER")      # e.g. lab12bot@gmail.com
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")    # 16‑char Google App‑Password
ADMIN_EMAIL    = os.getenv("ADMIN_EMAIL", EMAIL_SENDER)
EMAIL_SMTP     = "smtp.gmail.com"
EMAIL_PORT     = 465

if not (EMAIL_SENDER and EMAIL_PASSWORD):
    raise RuntimeError("Add EMAIL_SENDER & EMAIL_PASSWORD to your .env")

# ── tiny helpers ───────────────────────────────────────────────────────────
def _build(msg_to: str, subject: str, plain: str, html: str | None = None) -> EmailMessage:
    m              = EmailMessage()
    m["From"]      = EMAIL_SENDER
    m["To"]        = msg_to
    m["Subject"]   = subject
    m["Reply-To"] = EMAIL_SENDER
    m["List-Unsubscribe"] = "<mailto:{}?subject=unsubscribe>".format(EMAIL_SENDER)
    m["X-Mailing-Server"] = "Lab12 Mailer"
    m.set_content(plain)
    if html:
        m.add_alternative(html, subtype="html")
    return m

async def _deliver(msg: EmailMessage) -> None:
    print('delivering...')
    ctx = ssl.create_default_context(cafile=certifi.where())
    loop = asyncio.get_running_loop()

    # put *all* the blocking SMTP work inside this helper
    def _blocking():
        try:
            with smtplib.SMTP_SSL(EMAIL_SMTP, EMAIL_PORT, context=ctx) as s:
                # s.set_debuglevel(1)            # SMTP protocol debug
                s.login(EMAIL_SENDER, EMAIL_PASSWORD)
                s.send_message(msg)
            print("✅ [blocking] Email sent successfully")
        except Exception:
            print("❌ [blocking] Failed to send email:")
            traceback.print_exc()
            raise

    # now offload it to a thread
    try:
        await loop.run_in_executor(None, _blocking)
        print("✅ Email sent successfully (async)")
    except Exception as e:
        print(f"❌ Failed in run_in_executor: {e}")
        traceback.print_exc()
        raise
# ── public API ─────────────────────────────────────────────────────────────
async def send_verification_email(recipient: str, code: str, public_base_url: str) -> None:
    print(f"Entered send_verification_email for recipient: {recipient} with code: {code}") # <-- LOG POINT A (Function Entry)
    link      = f"{public_base_url}/verify?pin={code}&email={recipient}"
    expires   = (datetime.utcnow() + timedelta(days=1)).strftime("%B %d %Y")
    subject   = "Verify your Lab12 e‑mail"
    plain     = f"Your verification code is {code} (expires {expires}).\nOr open {link}"
    html      = f"""\
<!doctype html><html><head><meta charset="utf-8">
<style>body{{font-family:Helvetica,Arial,sans-serif}}
.container{{border:1px solid #ccc;padding:20px;border-radius:6px;max-width:500px;margin:auto}}
.code{{font-size:32px;text-align:center;margin:18px 0}}
.btn{{display:block;width:200px;margin:18px auto;text-align:center;background:#1a73e8;color:#fff;
      text-decoration:none;padding:12px 0;border-radius:4px}}</style></head><body>
<div class="container">
  <h1 style="text-align:center;margin:0 0 18px">Verify e‑mail</h1>
  <p style="text-align:center">Use this 6‑digit code:</p>
  <div class="code">{code}</div>
  <p style="text-align:center;font-size:13px;color:#d40000">Expires {expires}. After that you’ll need a new code.</p></div></body></html>"""

    await _deliver(_build(recipient, subject, plain, html))

async def send_feedback_alert(feedback: str, user_email: str) -> None:
    subject = f"New Lab12 feedback from {user_email}"
    plain   = feedback
    html    = f"<p><strong>From</strong>: {bleach.clean(user_email)}</p><pre>{bleach.clean(feedback)}</pre>"
    await _deliver(_build(ADMIN_EMAIL, subject, plain, html))