"""Semi-automatic Google Takeout helper — BEST-EFFORT, full automation impossible.

Google exposes NO Takeout API. An export MUST be user-triggered at
takeout.google.com (interactive, CAPTCHA-gated, no programmatic create). So this
module is a two-phase assist, not an automation:

1. request_takeout() -> prints the Takeout URL + steps for the human to run.
2. watch_for_export(provider, account) -> once the human triggered it, polls Gmail
   (via the provider's mail()) for the "Your Google data is ready" email, extracts
   the download link(s), and downloads what it can:
     - Drive links (Takeout "save to Drive" option) -> downloaded via the provider's
       files() using the account's OAuth creds.
     - Direct takeout.google.com/download links -> PRINTED, not fetched: those are
       gated by browser session cookies the OAuth token can't supply, so the human
       clicks them in a browser.

data_portability_export() is a stub over the Data Portability API (scope
`dataportability.myactivity.search` is already granted in google_auth.SCOPES). That
API is the CLOSEST thing to a real Takeout API — initiate/poll/retrieve archives
programmatically — but it covers only a subset of Takeout products and needs
per-scope grants, so it is NOT a drop-in replacement.
"""
from __future__ import annotations

import base64
import re
import time
from pathlib import Path
from typing import Any

TAKEOUT_URL = "https://takeout.google.com/"

_READY_QUERY = (
    'from:google.com (subject:"Your Google data is ready" OR subject:takeout OR '
    'subject:"data archive")'
)
_DRIVE_RE = re.compile(
    r"https://drive\.google\.com/(?:file/d/|[^/]*?[?&]id=)([\w-]{10,})")
_TAKEOUT_DL_RE = re.compile(r"https://takeout\.google\.com/\S*download\S*")


def request_takeout() -> dict[str, Any]:
    steps = [
        f"Open {TAKEOUT_URL} (signed in as the target account)",
        "Deselect all, then select only the products you want",
        "Choose delivery: 'Send download link via email' OR 'Add to Drive'",
        "Pick 'Export once', .zip, and a size (2/4/10/50 GB split)",
        "Create export — Google emails 'Your Google data is ready' (minutes to 48h)",
        "Then run watch_for_export(provider, account) to auto-collect the archives",
    ]
    print(f"Google Takeout must be started by hand — no API exists.\nURL: {TAKEOUT_URL}")
    for i, s in enumerate(steps, 1):
        print(f"  {i}. {s}")
    return {"url": TAKEOUT_URL, "steps": steps, "automatable": False}


def _message_text(mail: Any, msg_id: str) -> str:
    """Full readable text of a message: prefer canonical .body, fall back to
    decoding the raw payload the adapter stashed in .extra."""
    msg = mail.read(msg_id)
    if getattr(msg, "body", None):
        return msg.body
    return _decode_payload((msg.extra or {}).get("payload", {}))


def _decode_payload(payload: dict) -> str:
    out = []

    def walk(part: dict) -> None:
        data = part.get("body", {}).get("data")
        if data:
            out.append(base64.urlsafe_b64decode(data).decode("utf-8", "replace"))
        for sub in part.get("parts", []) or []:
            walk(sub)

    walk(payload)
    return "\n".join(out)


def _extract_links(text: str) -> tuple[list[str], list[str]]:
    """(drive_file_ids, manual_download_urls) from the email body."""
    ids = set(_DRIVE_RE.findall(text))
    manual = sorted(set(_TAKEOUT_DL_RE.findall(text)))
    return sorted(ids), manual


def watch_for_export(google_provider: Any, account: str | None = None,
                     poll_seconds: int = 600, timeout_hours: int = 48,
                     out_dir: str = "takeout") -> dict[str, Any]:
    """Poll Gmail for the Takeout-ready email; download Drive archives, print the rest.

    Returns {downloaded: [paths], manual_links: [urls], message_id, polls}.
    Blocks up to timeout_hours, sleeping poll_seconds between checks.
    """
    mail = google_provider.mail()
    files = google_provider.files()
    dest = Path(out_dir)
    dest.mkdir(parents=True, exist_ok=True)

    deadline = time.monotonic() + timeout_hours * 3600
    polls = 0
    while True:
        polls += 1
        for env in mail.search(_READY_QUERY, max_results=10):
            drive_ids, manual = _extract_links(_message_text(mail, env.id))
            if not drive_ids and not manual:
                continue
            downloaded = []
            for fid in drive_ids:
                target = str(dest / f"takeout-{fid}.zip")
                downloaded.append(files.download(fid, target))
            for url in manual:
                print(f"Manual download (needs browser cookies): {url}")
            return {"downloaded": downloaded, "manual_links": manual,
                    "message_id": env.id, "polls": polls}
        if time.monotonic() >= deadline:
            return {"downloaded": [], "manual_links": [], "message_id": None,
                    "polls": polls, "timed_out": True}
        time.sleep(poll_seconds)


def data_portability_export(resources: list[str], account: str | None = None) -> dict[str, Any]:
    """Stub: initiate a Data Portability archive — closest thing to a Takeout API.

    Uses the already-granted dataportability scope. `resources` = data-portability
    resource names (e.g. "myactivity.search"). Returns the initiate response
    ({archiveJobId, ...}); poll archiveJobs.getPortabilityArchiveState +
    fetch signed URLs to complete. Covers a SUBSET of Takeout products only.
    """
    from gsuite_agent import google_auth

    svc = google_auth.service("dataportability", "v1", account=account)
    return svc.portabilityArchive().initiate(
        body={"resources": resources}).execute()
