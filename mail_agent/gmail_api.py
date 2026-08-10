"""Gmail API (OAuth2) backend — the universal path: send + read + search + download.

Works on personal AND Workspace accounts, send + read in one scoped token, no
password, revocable. This is the recommended backend (App Password/SMTP is
send-only; himalaya needs a binary). Drop-in for mail.py's interface, so the CAS
module works unchanged.

One-time setup:
1. console.cloud.google.com -> new project -> enable Gmail API.
2. OAuth consent screen -> External -> add your Gmail as a test user.
3. Credentials -> OAuth client ID -> Desktop app -> download JSON to
   config/gmail-oauth-client.json.
4. First call opens a browser to authorize; token cached to
   config/gmail-token.json (git-ignored).

Scope gmail.modify = send + read + label (least privilege that covers CAS).
"""
from __future__ import annotations

import base64
import mimetypes
import os
from email.message import EmailMessage
from pathlib import Path

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
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
        _CFG.mkdir(exist_ok=True)
        TOKEN_FILE.write_text(creds.to_json())
    return build("gmail", "v1", credentials=creds)


# ---- send ----

def send(to: str, subject: str, body: str, attachments: list[str] | None = None,
         sender: str | None = None) -> str:
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
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    sent = _service().users().messages().send(userId="me", body={"raw": raw}).execute()
    return sent["id"]


# ---- read / search (interface-compatible with mail.py) ----

def _summary(svc, mid: str) -> dict:
    m = svc.users().messages().get(userId="me", id=mid, format="metadata",
                                   metadataHeaders=["From", "Subject", "Date"]).execute()
    h = {x["name"]: x["value"] for x in m.get("payload", {}).get("headers", [])}
    return {"id": mid, "from": h.get("From", ""), "subject": h.get("Subject", ""),
            "date": h.get("Date", ""), "snippet": m.get("snippet", "")}


def search(query: str, max_results: int = 50) -> list[dict]:
    svc = _service()
    r = svc.users().messages().list(userId="me", q=query, maxResults=max_results).execute()
    return [_summary(svc, m["id"]) for m in r.get("messages", [])]


def list_inbox(mailbox: str = "INBOX", page: int = 1, page_size: int = 50) -> list[dict]:
    svc = _service()
    r = svc.users().messages().list(userId="me", labelIds=[mailbox],
                                    maxResults=page_size).execute()
    return [_summary(svc, m["id"]) for m in r.get("messages", [])]


def read(msg_id: str) -> dict:
    svc = _service()
    m = svc.users().messages().get(userId="me", id=msg_id, format="full").execute()
    return m


def download_attachments(msg_id: str, out_dir: str) -> list[str]:
    svc = _service()
    m = svc.users().messages().get(userId="me", id=msg_id, format="full").execute()
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    saved = []

    def walk(parts):
        for p in parts or []:
            fn = p.get("filename")
            body = p.get("body", {})
            if fn and body.get("attachmentId"):
                data = svc.users().messages().attachments().get(
                    userId="me", messageId=msg_id, id=body["attachmentId"]).execute()
                raw = base64.urlsafe_b64decode(data["data"])
                dest = out / fn
                dest.write_bytes(raw)
                saved.append(str(dest))
            walk(p.get("parts"))

    walk(m.get("payload", {}).get("parts"))
    return saved
