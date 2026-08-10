"""Unified Google OAuth2 — ONE token per ACCOUNT, ALL scopes.

Multi-account (primary = you@ = Google-apps identity; secondary =
second@ = your projects). One OAuth client, a token per account,
selected by name (env GOOGLE_ACCOUNT or account= arg).

Pure Python (google-api-python-client) — works on this DLP-locked AVD where
standalone binaries like gog.exe are blocked. rclone handles Drive files.

.env:
    GOOGLE_ACCOUNTS=chirag,why
    GOOGLE_ACCOUNT_primary=you@gmail.com
    GOOGLE_ACCOUNT_secondary=second@gmail.com
    GOOGLE_ACCOUNT=why

Setup once: Cloud project 'gsuite-agent' -> enable Gmail/Drive/Docs/Sheets/
Calendar APIs -> OAuth consent (add both emails as test users) -> Desktop OAuth
client -> config/google-oauth-client.json. First call per account = browser
consent; token cached config/token-<account>.json.
"""
from __future__ import annotations

import os
os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")
from pathlib import Path

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",       # read + send + labels
    "https://mail.google.com/",                            # full mail (delete, all IMAP-equiv)
    "https://www.googleapis.com/auth/drive",               # full Drive
    "https://www.googleapis.com/auth/documents",           # Docs
    "https://www.googleapis.com/auth/spreadsheets",        # Sheets
    "https://www.googleapis.com/auth/presentations",       # Slides
    "https://www.googleapis.com/auth/calendar",            # Calendar (read + change)
    "https://www.googleapis.com/auth/contacts",            # Contacts
    "https://www.googleapis.com/auth/tasks",               # Tasks
    "https://www.googleapis.com/auth/photoslibrary.readonly",  # Photos (read)
    # NOTE: dataportability.* scopes CANNOT mix with other scopes (Google rejects
    # the combined consent). Portability/Takeout uses its own separate token — see
    # DATA_PORTABILITY_SCOPES + credentials(scopes=...) for that isolated flow.
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/userinfo.email",
]

_CFG = Path(__file__).resolve().parent.parent / "config"
CLIENT_SECRET = _CFG / "google-oauth-client.json"


def _load_env() -> None:
    envf = _CFG.parent / ".env"
    if envf.exists():
        for line in envf.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def _account(account: str | None) -> str:
    if account:
        return account
    _load_env()
    return os.environ.get("GOOGLE_ACCOUNT", "default")


def _token_file(account: str) -> Path:
    return _CFG / f"token-{account}.json"


def credentials(account: str | None = None):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    acct = _account(account)
    tok = _token_file(acct)
    creds = None
    if tok.exists():
        creds = Credentials.from_authorized_user_file(str(tok), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CLIENT_SECRET.exists():
                raise FileNotFoundError(
                    f"OAuth client secret missing at {CLIENT_SECRET} — see module docstring"
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), SCOPES)
            email = os.environ.get(f"GOOGLE_ACCOUNT_{acct}")
            kw = {"login_hint": email} if email else {}
            creds = flow.run_local_server(port=0, **kw)
        _CFG.mkdir(exist_ok=True)
        tok.write_text(creds.to_json())
    return creds


def service(api: str, version: str, account: str | None = None):
    from googleapiclient.discovery import build
    return build(api, version, credentials=credentials(account))


def accounts() -> list[str]:
    _load_env()
    return [a.strip() for a in os.environ.get("GOOGLE_ACCOUNTS", "").split(",") if a.strip()]


def clear_token(account: str | None = None) -> bool:
    """Delete the cached OAuth token for an account (forces re-consent next call).
    Server-side revoke is separate: myaccount.google.com/permissions."""
    tok = _token_file(_account(account))
    if tok.exists():
        tok.unlink()
        return True
    return False
