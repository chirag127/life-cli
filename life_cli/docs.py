"""Google Docs — create/read/append/replace/export via the shared OAuth token.

Auth = google_auth.service(...); one token per account, account= selects it.
Export goes through Drive files().export (Docs API can't render binaries).
"""
from __future__ import annotations

import io
from pathlib import Path

from . import google_auth


def _docs(account=None):
    return google_auth.service("docs", "v1", account)


def _drive(account=None):
    return google_auth.service("drive", "v3", account)


def create(title, body_text="", account=None):
    doc = _docs(account).documents().create(body={"title": title}).execute()
    doc_id = doc["documentId"]
    if body_text:
        append_text(doc_id, body_text, account)
    return doc_id


def read(doc_id, account=None):
    doc = _docs(account).documents().get(documentId=doc_id).execute()
    out = []
    for el in doc.get("body", {}).get("content", []):
        for run in el.get("paragraph", {}).get("elements", []):
            out.append(run.get("textRun", {}).get("content", ""))
    return "".join(out)


def append_text(doc_id, text, account=None):
    _docs(account).documents().batchUpdate(
        documentId=doc_id,
        body={"requests": [{"insertText": {"endOfSegmentLocation": {}, "text": text}}]},
    ).execute()


def replace_text(doc_id, find, replace, account=None):
    _docs(account).documents().batchUpdate(
        documentId=doc_id,
        body={"requests": [{"replaceAllText": {
            "containsText": {"text": find, "matchCase": True},
            "replaceText": replace,
        }}]},
    ).execute()


def export(doc_id, dest_path, mime="application/pdf", account=None):
    from googleapiclient.http import MediaIoBaseDownload

    req = _drive(account).files().export_media(fileId=doc_id, mimeType=mime)
    buf = io.BytesIO()
    dl = MediaIoBaseDownload(buf, req)
    done = False
    while not done:
        _, done = dl.next_chunk()
    dest = Path(dest_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(buf.getvalue())
    return str(dest)
