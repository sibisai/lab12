# Privacy Policy for Lab12

**Last updated: May 5, 2025**

---

## 1. Introduction

Lab12 (“we”, “us”, or “our”) provides offline streaming transcription and AI-generated lecture notes through our web application. We respect your privacy and are committed to protecting your personal data. This Privacy Policy explains what information we collect, how we use it, and your rights.

---

## 2. Information We Collect

**Account Data:** When you register, we collect your username, email address, and hashed password.  
**Usage Data:** We log API calls (e.g. `/summarize`, `/save-to-drive`), WebSocket connections, rate-limit counters, and timestamps.  
**Transcripts & Notes:** Your audio transcripts and AI-generated notes are stored locally in your browser's storage. We do **not** store these by default on our servers.  
**Email & Support:** If you opt in for verification emails or password resets, we collect your email address and send transactional emails via SendGrid.  
**Google Drive Integration:** With your explicit consent, we receive a temporary OAuth token and folder ID to upload notes to your Drive. We do **not** store long-term Google credentials.

---

## 3. How We Use Your Data

**Authentication & Security:** To authenticate you via JWTs and protect your account.  
**API Functionality:** To power transcription, summarization, and saving to Google Drive.  
**Rate Limiting:** To enforce per-minute and per-day quotas and prevent abuse.  
**Communication:** To send you registration, verification, and password-reset emails.

---

## 4. Data Storage & Security

**Passwords:** Stored only as bcrypt hashes in PostgreSQL.  
**Sessions & Logs:** Stored in PostgreSQL (and optionally Redis for rate limits).  
**Local Storage:** Transcripts and notes remain in your browser unless you explicitly save them elsewhere.  
**Transport Security:** All data in transit is encrypted via HTTPS/TLS.

---

## 5. Third-Party Services

**OpenAI API:** We send transcript text to OpenAI for note generation; refer to OpenAI's Privacy Policy for details.  
**Google Drive API:** We use your OAuth token to create Google Docs; see Google's Privacy Policy.  
**SendGrid:** For transactional emails; see SendGrid's Privacy Policy.

---

## 6. Your Rights & Choices

**Access & Correction:** You can view or update your account details via the `/me` endpoint.  
**Data Deletion:** To delete your account (and remove your email/password), contact us at privacy@lab12note.com. Local storage data can be cleared in your browser settings.  
**Opt-Out:** You may disable email notifications by updating your preferences in the app.

---

## 7. Children's Privacy

Lab12 is not intended for use by children under 13. We do not knowingly collect data from minors.

---

## 8. Changes to This Policy

We may update this policy occasionally. We'll post changes here with a new “Last updated” date.

---

## 9. Contact Us

If you have questions or concerns about this Privacy Policy, please email privacy@lab12note.com.
