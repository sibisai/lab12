# mailer.py — Reusable async helpers for Lab12 e‑mail, now using SendGrid Web API

import os
import asyncio
import traceback
from datetime import datetime, timedelta

import bleach
from dotenv import load_dotenv, find_dotenv
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

# ── env ────────────────────────────────────────────────────────────────────
load_dotenv(find_dotenv(), override=True)

SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
EMAIL_SENDER     = os.getenv("EMAIL_SENDER")      # e.g. no‑reply@yourdomain.com
ADMIN_EMAIL      = os.getenv("ADMIN_EMAIL", EMAIL_SENDER)

if not (SENDGRID_API_KEY and EMAIL_SENDER):
    raise RuntimeError("Add SENDGRID_API_KEY & EMAIL_SENDER to your .env")

# ── internal send helper ────────────────────────────────────────────────────
async def _send_via_sendgrid(to_email: str, subject: str, plain: str, html: str | None = None) -> None:
    """
    Fire off a SendGrid Mail object.  Uses asyncio to keep the API call non‑blocking.
    """
    message = Mail(
        from_email=EMAIL_SENDER,
        to_emails=to_email,
        subject=subject,
        plain_text_content=plain,
        html_content=html or plain,
    )

    loop = asyncio.get_running_loop()
    def _blocking_send():
        try:
            sg = SendGridAPIClient(SENDGRID_API_KEY)
            response = sg.send(message)
            print(f"✅ [SendGrid] {to_email!r} → {subject!r}: {response.status_code}")
        except Exception:
            print(f"❌ [SendGrid] Failed to send to {to_email!r} / {subject!r}")
            traceback.print_exc()
            raise

    await loop.run_in_executor(None, _blocking_send)

# ── public API ─────────────────────────────────────────────────────────────
async def send_verification_email(recipient: str, code: str, public_base_url: str) -> None:
    """
    Send a 6‑digit PIN with deep‑link verification button.
    """
    print(f"[INFO] send_verification_email for {recipient!r} code={code}")
    expires_date = (datetime.utcnow() + timedelta(days=1)).strftime("%B %d %Y")
    link         = f"{public_base_url}/verify?pin={code}&email={recipient}"

    subject = "Verify your Lab12 e‑mail"
    plain   = (
        f"Your verification code is {code} (expires {expires_date}).\n"
        f"Or click: {link}"
    )
    html    = f"""\
<!doctype html>
<html><head><meta charset="utf-8">
  <style>
    body {{ font-family: Helvetica, Arial, sans-serif; }}
    .container {{ border: 1px solid #ccc; padding:20px; border-radius:6px; max-width:500px; margin:auto }}
    .code {{ font-size:32px; text-align:center; margin:18px 0 }}

    .expires {{ text-align:center; font-size:13px; color:#d40000 }}
  </style>
</head><body>
  <div class="container">
    <h1 style="text-align:center; margin:0 0 18px">Verify email</h1>
    <p style="text-align:center">Use this 6‑digit code:</p>
    <div class="code">{code}</div>
    <p class="expires">Expires {expires_date}</p>
    
  </div>
</body></html>"""

    await _send_via_sendgrid(recipient, subject, plain, html)

"""
    .btn {{
      display:block; width:200px; margin:18px auto;
      text-align:center; background:#1a73e8; color:#fff;
      text-decoration:none; padding:12px 0; border-radius:4px
    }}
 <a class="btn" href="{link}">Verify now</a>
"""

async def send_feedback_alert(feedback: str, user_email: str) -> None:
    """
    Send moderators a copy of user feedback.
    """
    print(f"[INFO] send_feedback_alert from {user_email!r}")
    subject = f"New Lab12 feedback from {user_email}"
    clean_user = bleach.clean(user_email)
    clean_fb   = bleach.clean(feedback)
    plain = clean_fb
    html  = (
        f"<p><strong>From:</strong> {clean_user}</p>"
        f"<pre style='white-space:pre-wrap'>{clean_fb}</pre>"
    )
    await _send_via_sendgrid(ADMIN_EMAIL, subject, plain, html)


async def send_password_reset_email(recipient: str, code: str) -> None:
    """
    Send a 6‑digit password reset code.
    """
    print(f"[INFO] send_password_reset_email for {recipient!r} code={code}")
    expires_at = (datetime.utcnow() + timedelta(hours=1)).strftime("%B %d, %Y at %I:%M %p UTC")

    subject = "Your Lab12 password‑reset code"
    plain   = (
        f"Your Lab12 password‑reset code is {code}.\n"
        f"It expires at {expires_at}.\n"
    )
    html = f"""\
<!doctype html>
<html><head><meta charset="utf-8">
  <style>
    body {{ font-family: Helvetica, Arial, sans-serif; }}
    .container {{ border: 1px solid #ccc; padding:20px; border-radius:6px; max-width:500px; margin:auto }}
    .code {{ font-size:32px; text-align:center; margin:18px 0; font-weight:bold }}
    .expires {{ text-align:center; font-size:13px; color:#d40000 }}
  </style>
</head><body>
  <div class="container">
    <h1 style="text-align:center; margin:0 0 18px">Reset your password</h1>
    <p style="text-align:center">Use this 6‑digit code:</p>
    <div class="code">{code}</div>
    <p class="expires">Expires {expires_at}</p>
  </div>
</body></html>"""

    await _send_via_sendgrid(recipient, subject, plain, html)


async def send_user_verified_alert(
    user_email: str,
    full_name: str | None = None,
    total_verified: int = 0
) -> None:
    from datetime import datetime
    import bleach

    when = datetime.utcnow().strftime("%B %d, %Y at %I:%M %p UTC")
    clean_email = bleach.clean(user_email)
    clean_name  = bleach.clean(full_name) if full_name else "–"
    subject = f"[Lab12] New user verified: {clean_email}"
    plain = (
        f"User verified their address:\n\n"
        f" • Email           : {clean_email}\n"
        f" • Name            : {clean_name}\n"
        f" • When            : {when}\n"
        f" • Total verified  : {total_verified}\n"
    )
    html = (
        f"<p><strong>User verified their address:</strong></p>"
        f"<ul>"
        f"  <li><strong>Email:</strong> {clean_email}</li>"
        f"  <li><strong>Name:</strong> {clean_name}</li>"
        f"  <li><strong>When:</strong> {when}</li>"
        f"  <li><strong>Total verified users:</strong> {total_verified}</li>"
        f"</ul>"
    )
    await _send_via_sendgrid(ADMIN_EMAIL, subject, plain, html)