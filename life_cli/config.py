from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
RENDERED_CONFIG = CONFIG_DIR / "himalaya-config.toml"

load_dotenv(ROOT / ".env")


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class Config:
    gmail_user: str
    gmail_app_password: str
    investor_pan: str
    registered_email: str
    himalaya_config_path: Path

    @classmethod
    def load(cls) -> "Config":
        env = {k: (os.getenv(k) or "").strip() for k in _REQUIRED}
        missing = [k for k in _REQUIRED if not env[k]]
        if missing:
            raise ConfigError(f"missing env: {', '.join(missing)}")
        path = os.getenv("HIMALAYA_CONFIG_PATH", "").strip()
        return cls(
            gmail_user=env["GMAIL_USER"],
            gmail_app_password=env["GMAIL_APP_PASSWORD"],
            investor_pan=env["INVESTOR_PAN"],
            registered_email=env["REGISTERED_EMAIL"],
            himalaya_config_path=Path(path) if path else RENDERED_CONFIG,
        )


_REQUIRED = ("GMAIL_USER", "GMAIL_APP_PASSWORD", "INVESTOR_PAN", "REGISTERED_EMAIL")


def render_himalaya_config(cfg: Config, dest: Path | None = None) -> Path:
    dest = dest or RENDERED_CONFIG
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(_toml(cfg), encoding="utf-8")
    return dest


def _toml(cfg: Config) -> str:
    user = _q(cfg.gmail_user)
    pw = _q(cfg.gmail_app_password)
    return f"""[accounts.gmail]
default = true
email = {user}

imap.server = "imaps://imap.gmail.com:993"
imap.sasl.plain.username = {user}
imap.sasl.plain.password.raw = {pw}

smtp.server = "smtp://smtp.gmail.com:587"
smtp.starttls = true
smtp.sasl.plain.username = {user}
smtp.sasl.plain.password.raw = {pw}

mailbox.alias.inbox = "INBOX"
mailbox.alias.sent = "[Gmail]/Sent Mail"
mailbox.alias.drafts = "[Gmail]/Drafts"
mailbox.alias.trash = "[Gmail]/Trash"
mailbox.alias.archive = "[Gmail]/All Mail"
"""


def _q(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
