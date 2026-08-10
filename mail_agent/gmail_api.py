"""Gmail API sender (OAuth2) — alternative to the Himalaya SMTP path.

Setup (one-time):
1. Google Cloud Console -> new project -> enable Gmail API.
2. OAuth consent screen (External, add yourself as test user).
3. Credentials -> OAuth client ID -> Desktop app -> download to
   config/gmail-oauth-client.json.
4. First send() opens a browser to authorize; token cached to
   config/gmail-token.json (git-ignored).

Scope: gmail.send only (least privilege — can send, cannot read).
"""
from __future__ import annotations

import base64
import mimetypes
import os
from email.message import EmailMessage
from pathlib import Path

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
_CFG = Path(__file__).resolve().parent.parent / "config"
CLIENT_SECRET = _CFG / "gmail-oauth-client.json"
TOKEN_FILE = _CFG / "gmail-token.json"


def _service():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CLIENT_SECRET.exists():
                raise FileNotFoundError(
                    f"OAuth client secret missing at {CLIENT_SECRET} — see module docstring"
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_FILE.write_text(creds.to_json())
    return build("gmail", "v1", credentials=creds)


def _build(to: str, subject: str, body: str, sender: str | None = None,
           attachments: list[str] | None = None) -> dict:
    msg = EmailMessage()
    msg["To"] = to
    if sender:
        msg["From"] = sender
    msg["Subject"] = subject
    msg.set_content(body)
    for path in attachments or []:
        ctype, _ = mimetypes.guess_type(path)
        maintype, subtype = (ctype or "application/octet-stream").split("/", 1)
        with open(path, "rb") as f:
            msg.add_attachment(f.read(), maintype=maintype, subtype=subtype,
                               filename=os.path.basename(path))
    return {"raw": base64.urlsafe_b64encode(msg.as_bytes()).decode()}


def send(to: str, subject: str, body: str, attachments: list[str] | None = None,
         sender: str | None = None) -> str:
    """Send via Gmail API. Returns the sent message id."""
    svc = _service()
    sent = svc.users().messages().send(
        userId="me", body=_build(to, subject, body, sender, attachments)
    ).execute()
    return sent["id"]
