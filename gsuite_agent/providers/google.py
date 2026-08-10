"""GoogleProvider — maps the thin Google modules into the canonical protocol.

Wraps gmail_api / drive / calendar / contacts (People API) and converts their
dict/native shapes into core.models dataclasses. One account per provider
instance (account=None -> google_auth resolves env GOOGLE_ACCOUNT).
"""
from __future__ import annotations

import base64
from datetime import datetime
from email.utils import parsedate_to_datetime

from gsuite_agent import calendar as calendar_mod
from gsuite_agent import contacts as contacts_mod
from gsuite_agent import drive as drive_mod
from gsuite_agent import gmail_api
from gsuite_agent.core.models import CalendarEvent, Contact, DriveFile, Message
from gsuite_agent.core.provider import Provider


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _headers(payload: dict) -> dict[str, str]:
    return {h["name"]: h["value"] for h in payload.get("headers", [])}


def _body_text(payload: dict) -> str:
    def walk(part: dict) -> str | None:
        if part.get("mimeType") == "text/plain":
            data = part.get("body", {}).get("data")
            if data:
                return base64.urlsafe_b64decode(data).decode("utf-8", "replace")
        for sub in part.get("parts", []):
            found = walk(sub)
            if found is not None:
                return found
        return None

    return walk(payload) or ""


def _summary_to_message(d: dict) -> Message:
    return Message(
        id=d["id"], thread_id=None, sender=d.get("from", ""), to=[],
        subject=d.get("subject", ""), snippet=d.get("snippet", ""),
        date=_parse_date(d.get("date")),
    )


def _full_to_message(m: dict) -> Message:
    payload = m.get("payload", {})
    h = _headers(payload)
    labels = m.get("labelIds", [])
    return Message(
        id=m["id"], thread_id=m.get("threadId"), sender=h.get("From", ""),
        to=[a.strip() for a in h.get("To", "").split(",") if a.strip()],
        subject=h.get("Subject", ""), snippet=m.get("snippet", ""),
        body=_body_text(payload), date=_parse_date(h.get("Date")),
        folder=labels[0] if labels else None, unread="UNREAD" in labels,
        has_attachments=any(p.get("filename") for p in payload.get("parts", [])),
        extra={"labelIds": labels},
    )


class _Mail:
    def __init__(self, account: str | None):
        self._account = account

    def send(self, to: str, subject: str, body: str,
             attachments: list[str] | None = None) -> str:
        return gmail_api.send(to, subject, body, attachments, account=self._account)

    def search(self, query: str, max_results: int = 50) -> list[Message]:
        return [_summary_to_message(d)
                for d in gmail_api.search(query, max_results, account=self._account)]

    def list_inbox(self, page_size: int = 50) -> list[Message]:
        return [_summary_to_message(d)
                for d in gmail_api.list_inbox(page_size=page_size, account=self._account)]

    def read(self, msg_id: str) -> Message:
        return _full_to_message(gmail_api.read(msg_id, account=self._account))

    def download_attachments(self, msg_id: str, out_dir: str) -> list[str]:
        return gmail_api.download_attachments(msg_id, out_dir, account=self._account)


class _Calendar:
    def __init__(self, account: str | None):
        self._account = account

    def list_events(self, time_min=None, time_max=None,
                    max_results: int = 50) -> list[CalendarEvent]:
        return [self._to_event(e) for e in calendar_mod.list_events(
            time_min=time_min, time_max=time_max, max_results=max_results,
            account=self._account)]

    def create_event(self, ev: CalendarEvent) -> str:
        return calendar_mod.create_event(
            ev.summary, ev.start.isoformat(), ev.end.isoformat(),
            description=ev.description, attendees=ev.attendees,
            calendar_id=ev.calendar_id, account=self._account)

    def update_event(self, event_id: str, **fields) -> None:
        calendar_mod.update_event(event_id, account=self._account, **fields)

    def delete_event(self, event_id: str) -> None:
        calendar_mod.delete_event(event_id, account=self._account)

    @staticmethod
    def _to_event(e: dict) -> CalendarEvent:
        start = e.get("start", {})
        end = e.get("end", {})
        return CalendarEvent(
            id=e["id"], summary=e.get("summary", ""),
            start=_parse_iso(start.get("dateTime") or start.get("date")),
            end=_parse_iso(end.get("dateTime") or end.get("date")),
            description=e.get("description", ""), location=e.get("location", ""),
            attendees=[a.get("email", "") for a in e.get("attendees", [])],
            extra={"htmlLink": e.get("htmlLink")},
        )


class _Files:
    def __init__(self, account: str | None):
        self._account = account

    def list_files(self, query: str | None = None) -> list[DriveFile]:
        return [self._to_file(f)
                for f in drive_mod.list_files(query=query, account=self._account)]

    def download(self, file_id: str, dest_path: str) -> str:
        return drive_mod.download(file_id, dest_path, account=self._account)

    def upload(self, local_path: str, folder_id: str | None = None) -> str:
        return drive_mod.upload(local_path, folder_id=folder_id, account=self._account)

    def delete(self, file_id: str) -> None:
        drive_mod.delete(file_id, account=self._account)

    @staticmethod
    def _to_file(f: dict) -> DriveFile:
        size = f.get("size")
        parents = f.get("parents")
        return DriveFile(
            id=f["id"], name=f.get("name", ""), mime_type=f.get("mimeType", ""),
            size=int(size) if size is not None else None,
            modified=_parse_iso(f.get("modifiedTime")),
            is_folder=f.get("mimeType") == "application/vnd.google-apps.folder",
            parent_id=parents[0] if parents else None,
            extra={"webViewLink": f.get("webViewLink")},
        )


class _Contacts:
    def __init__(self, account: str | None):
        self._account = account

    def list_contacts(self) -> list[Contact]:
        return [self._to_contact(p)
                for p in contacts_mod.list_contacts(account=self._account)]

    @staticmethod
    def _to_contact(p: dict) -> Contact:
        names = p.get("names", [])
        return Contact(
            id=p.get("resourceName", ""),
            name=names[0].get("displayName", "") if names else "",
            emails=[e.get("value", "") for e in p.get("emailAddresses", [])],
            phones=[n.get("value", "") for n in p.get("phoneNumbers", [])],
        )


class GoogleProvider(Provider):
    name = "google"
    capabilities = {"mail": True, "calendar": True, "files": True,
                    "contacts": True, "labels": True}

    def __init__(self, account: str | None = None):
        self._account = account

    def mail(self) -> _Mail:
        return _Mail(self._account)

    def calendar(self) -> _Calendar:
        return _Calendar(self._account)

    def files(self) -> _Files:
        return _Files(self._account)

    def contacts(self) -> _Contacts:
        return _Contacts(self._account)
