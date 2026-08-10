"""Gmail API — send + read + search + download, per-account.

Uses shared google_auth (ONE OAuth token per account, all scopes). Account
selected by name (env GOOGLE_ACCOUNT or account= arg); passed straight to
google_auth.service. Never builds its own credentials.
"""
from __future__ import annotations

import base64
import mimetypes
import os
from email.message import EmailMessage
from pathlib import Path

from . import google_auth


def _service(account: str | None = None):
    return google_auth.service("gmail", "v1", account=account)


# ---- send ----

def send(to: str, subject: str, body: str, attachments: list[str] | None = None,
         sender: str | None = None, account: str | None = None) -> str:
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
    sent = _service(account).users().messages().send(userId="me", body={"raw": raw}).execute()
    return sent["id"]


# ---- read / search (interface-compatible with mail.py) ----

def _summary(svc, mid: str) -> dict:
    m = svc.users().messages().get(userId="me", id=mid, format="metadata",
                                   metadataHeaders=["From", "Subject", "Date"]).execute()
    h = {x["name"]: x["value"] for x in m.get("payload", {}).get("headers", [])}
    return {"id": mid, "from": h.get("From", ""), "subject": h.get("Subject", ""),
            "date": h.get("Date", ""), "snippet": m.get("snippet", "")}


def search(query: str, max_results: int = 50, account: str | None = None) -> list[dict]:
    svc = _service(account)
    r = svc.users().messages().list(userId="me", q=query, maxResults=max_results).execute()
    return [_summary(svc, m["id"]) for m in r.get("messages", [])]


def list_inbox(mailbox: str = "INBOX", page: int = 1, page_size: int = 50,
               account: str | None = None) -> list[dict]:
    svc = _service(account)
    r = svc.users().messages().list(userId="me", labelIds=[mailbox],
                                    maxResults=page_size).execute()
    return [_summary(svc, m["id"]) for m in r.get("messages", [])]


def read(msg_id: str, account: str | None = None) -> dict:
    svc = _service(account)
    return svc.users().messages().get(userId="me", id=msg_id, format="full").execute()


def download_attachments(msg_id: str, out_dir: str, account: str | None = None) -> list[str]:
    svc = _service(account)
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
