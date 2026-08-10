"""Pure-stdlib SMTP sender (Gmail App Password). No himalaya binary, no extra deps.

Simplest working send path when an App Password is available. For Gmail:
smtp.gmail.com:587 STARTTLS, username=GMAIL_USER, password=GMAIL_APP_PASSWORD.
"""
from __future__ import annotations

import mimetypes
import os
import smtplib
from email.message import EmailMessage
from pathlib import Path


def _creds() -> tuple[str, str]:
    user = os.environ.get("GMAIL_USER")
    pw = os.environ.get("GMAIL_APP_PASSWORD")
    if not user or not pw:
        envf = Path(__file__).resolve().parent.parent / ".env"
        if envf.exists():
            for line in envf.read_text(encoding="utf-8").splitlines():
                if line.startswith("GMAIL_USER=") and not user:
                    user = line.split("=", 1)[1].strip()
                elif line.startswith("GMAIL_APP_PASSWORD=") and not pw:
                    pw = line.split("=", 1)[1].strip()
    if not user or not pw:
        raise RuntimeError("set GMAIL_USER + GMAIL_APP_PASSWORD in .env")
    return user, pw


def send(to: str, subject: str, body: str, attachments: list[str] | None = None) -> None:
    """Send via Gmail SMTP with an App Password."""
    user, pw = _creds()
    msg = EmailMessage()
    msg["From"] = user
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    for path in attachments or []:
        ctype, _ = mimetypes.guess_type(path)
        maintype, subtype = (ctype or "application/octet-stream").split("/", 1)
        with open(path, "rb") as f:
            msg.add_attachment(f.read(), maintype=maintype, subtype=subtype,
                               filename=os.path.basename(path))
    with smtplib.SMTP("smtp.gmail.com", 587) as s:
        s.starttls()
        s.login(user, pw.replace(" ", ""))  # app passwords display with spaces
        s.send_message(msg)
