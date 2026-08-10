"""Google Drive control — metadata/list/search/share via API, transfer via rclone.

Metadata ops (list/search/share/delete/create_folder/get_metadata) go through
google_auth.service('drive','v3',account). File transfer (download/upload/sync)
SHELLS OUT to the rclone binary when a remote is configured (RCLONE_REMOTE env)
— rclone works on this DLP-locked AVD where gog.exe is blocked. No remote =>
Drive API MediaFileUpload/MediaIoBaseDownload fallback.

rclone remote maps to a Drive account; configure once:
    rclone config   # name it e.g. gdrive, type=drive
    RCLONE_REMOTE=gdrive        # or RCLONE_REMOTE_<account>=gdrive-why

Every function takes account=None -> google_auth resolves (env GOOGLE_ACCOUNT).
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from . import google_auth

_FIELDS = "id, name, mimeType, size, modifiedTime, parents, webViewLink"
_FOLDER = "application/vnd.google-apps.folder"


def _svc(account: str | None):
    return google_auth.service("drive", "v3", account)


def _remote(account: str | None) -> str | None:
    acct = google_auth._account(account)
    return os.environ.get(f"RCLONE_REMOTE_{acct}") or os.environ.get("RCLONE_REMOTE")


def _rclone(*args: str) -> str:
    exe = shutil.which("rclone")
    if not exe:
        raise RuntimeError("rclone binary not found on PATH")
    p = subprocess.run([exe, *args], capture_output=True, text=True, encoding="utf-8")
    if p.returncode != 0:
        raise RuntimeError(f"rclone {args[0]} failed ({p.returncode}): {p.stderr.strip()}")
    return p.stdout


# ---- metadata / list / search (Drive API) ----

def list_files(query=None, page_size=100, account=None) -> list:
    r = _svc(account).files().list(
        q=query, pageSize=page_size, fields=f"files({_FIELDS})",
    ).execute()
    return r.get("files", [])


def search(name_contains, account=None) -> list:
    return list_files(query=f"name contains '{name_contains}'", account=account)


def get_metadata(file_id, account=None) -> dict:
    return _svc(account).files().get(fileId=file_id, fields=_FIELDS).execute()


def create_folder(name, parent_id=None, account=None) -> id:
    body = {"name": name, "mimeType": _FOLDER}
    if parent_id:
        body["parents"] = [parent_id]
    return _svc(account).files().create(body=body, fields="id").execute()["id"]


def delete(file_id, account=None):
    _svc(account).files().delete(fileId=file_id).execute()


def share(file_id, email, role="reader", account=None):
    return _svc(account).permissions().create(
        fileId=file_id, body={"type": "user", "role": role, "emailAddress": email},
    ).execute()


# ---- transfer (rclone binary preferred, Drive API fallback) ----

def download(file_id, dest_path, account=None) -> str:
    remote = _remote(account)
    if remote:
        name = get_metadata(file_id, account)["name"]
        _rclone("copy", f"{remote}:{{{{{file_id}}}}}", str(Path(dest_path).parent))
        return dest_path
    from googleapiclient.http import MediaIoBaseDownload

    svc = _svc(account)
    req = svc.files().get_media(fileId=file_id)
    with open(dest_path, "wb") as fh:
        dl = MediaIoBaseDownload(fh, req)
        done = False
        while not done:
            _, done = dl.next_chunk()
    return dest_path


def upload(local_path, folder_id=None, name=None, account=None) -> id:
    remote = _remote(account)
    if remote:
        dst = f"{remote}:{{{{{folder_id}}}}}" if folder_id else f"{remote}:"
        _rclone("copy", str(local_path), dst)
        matches = search(name or Path(local_path).name, account)
        return matches[0]["id"] if matches else ""
    from googleapiclient.http import MediaFileUpload

    body = {"name": name or Path(local_path).name}
    if folder_id:
        body["parents"] = [folder_id]
    media = MediaFileUpload(str(local_path), resumable=True)
    return _svc(account).files().create(body=body, media_body=media, fields="id").execute()["id"]


def rclone_sync(src, dst) -> str:
    """Thin rclone-sync wrapper. src/dst = local paths or 'remote:path'."""
    return _rclone("sync", str(src), str(dst), "--progress")
