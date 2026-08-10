"""Thin wrapper around Himalaya v2 CLI. Parses --json output."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

HIMALAYA_CONFIG_PATH = str(Path(__file__).resolve().parent.parent / "config" / "config.toml")


def _bin() -> str:
    exe = shutil.which("himalaya")
    if not exe:
        raise RuntimeError("himalaya binary not found on PATH; install Himalaya v2 CLI")
    return exe


def _run(*args: str, capture: bool = True) -> str:
    cmd = [_bin(), "--json", "-c", HIMALAYA_CONFIG_PATH, *args]
    proc = subprocess.run(cmd, capture_output=capture, text=True, encoding="utf-8")
    if proc.returncode != 0:
        raise RuntimeError(f"himalaya {' '.join(args)} failed ({proc.returncode}): {proc.stderr.strip()}")
    return proc.stdout


def _json(*args: str) -> object:
    out = _run(*args).strip()
    return json.loads(out) if out else []


def list_inbox(mailbox: str = "inbox", page: int = 1, page_size: int = 50) -> list:
    return _json("envelope", "list", "-m", mailbox, "--page", str(page), "--page-size", str(page_size))


def search(query: str) -> list:
    return _json("envelope", "search", query)


def read(msg_id) -> dict:
    return _json("message", "read", str(msg_id))


def send(to: str, subject: str, body: str, attachments: list[str] | None = None) -> None:
    args = ["message", "compose", "--to", to, "--subject", subject, "--body", body]
    for path in attachments or []:
        args += ["--attachment", path]
    args.append("--send")
    _run(*args)


def download_attachments(msg_id, out_dir: str) -> list[str]:
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    before = set(Path(out_dir).iterdir())
    _run("attachment", "download", str(msg_id), "--downloads-dir", out_dir)
    return [str(p) for p in Path(out_dir).iterdir() if p not in before]


def list_mailboxes() -> list:
    return _json("mailbox", "list")
