"""Google provider — wraps existing thin modules (gmail_api, drive, calendar) and
maps their native dicts to canonical dataclasses. Contacts via People API directly.

No SDK re-implementation: mail/calendar/files delegate to the module functions;
each carries the account so google_auth resolves the right token.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from gsuite_agent import calendar as gcal
from gsuite_agent import drive as gdrive
from gsuite_agent import gmail_api
from gsuite_agent import google_auth
from gsuite_agent.core.models import CalendarEvent, Contact, DriveFile, Message
from gsuite_agent.core.provider import Provider


def _dt(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


class _Mail:
    def __init__(self, account: str | None):
        self._a = account

    def send(self, to, subject, body, attachments=None):
        return gmail_api.send(to, subject, body, attachments, account=self._a)

    def search(self, query, max_results=50):
        return [_msg(m) for m in gmail_api.search(query, max_results, account=self._a)]

    def list_inbox(self, page_size=50):
        return [_msg(m) for m in gmail_api.list_inbox(page_size=page_size, account=self._a)]

    def read(self, msg_id):
        raw = gmail_api.read(msg_id, account=self._a)
        h = {x["name"]: x["value"]
             for x in raw.get("payload", {}).get("headers", [])}
        return Message(
            id=raw.get("id", msg_id), thread_id=raw.get("threadId"),
            sender=h.get("From", ""), to=[t for t in h.get("To", "").split(",") if t],
            subject=h.get("Subject", ""), snippet=raw.get("snippet", ""),
            date=_dt(h.get("Date")),
            unread="UNREAD" in raw.get("labelIds", []),
            folder=next(iter(raw.get("labelIds", [])), None), extra=raw)

    def download_attachments(self, msg_id, out_dir):
        return gmail_api.download_attachments(msg_id, out_dir, account=self._a)


def _msg(d: dict[str, Any]) -> Message:
    return Message(
        id=d["id"], thread_id=d.get("threadId"), sender=d.get("from", ""),
        to=[], subject=d.get("subject", ""), snippet=d.get("snippet", ""),
        date=_dt(d.get("date")), extra=d)


class _Calendar:
    def __init__(self, account: str | None):
        self._a = account

    def list_events(self, time_min=None, time_max=None, max_results=50):
        raw = gcal.list_events(time_min=time_min, time_max=time_max,
                               max_results=max_results, account=self._a)
        return [_event(e) for e in raw]

    def create_event(self, ev: CalendarEvent):
        return gcal.create_event(
            ev.summary, ev.start.isoformat(), ev.end.isoformat(),
            description=ev.description, attendees=ev.attendees or None,
            calendar_id=ev.calendar_id, account=self._a)

    def update_event(self, event_id, **fields):
        gcal.update_event(event_id, account=self._a, **fields)

    def delete_event(self, event_id):
        gcal.delete_event(event_id, account=self._a)


def _event(e: dict[str, Any]) -> CalendarEvent:
    start = e.get("start", {})
    end = e.get("end", {})
    return CalendarEvent(
        id=e["id"], summary=e.get("summary", ""),
        start=_dt(start.get("dateTime") or start.get("date")) or datetime.min,
        end=_dt(end.get("dateTime") or end.get("date")) or datetime.min,
        description=e.get("description", ""), location=e.get("location", ""),
        attendees=[a.get("email", "") for a in e.get("attendees", [])],
        extra=e)


class _Files:
    def __init__(self, account: str | None):
        self._a = account

    def list_files(self, query=None):
        return [_file(f) for f in gdrive.list_files(query=query, account=self._a)]

    def download(self, file_id, dest_path):
        return gdrive.download(file_id, dest_path, account=self._a)

    def upload(self, local_path, folder_id=None):
        return gdrive.upload(local_path, folder_id=folder_id, account=self._a)

    def delete(self, file_id):
        gdrive.delete(file_id, account=self._a)


def _file(f: dict[str, Any]) -> DriveFile:
    size = f.get("size")
    return DriveFile(
        id=f["id"], name=f.get("name", ""), mime_type=f.get("mimeType", ""),
        size=int(size) if size is not None else None,
        modified=_dt(f.get("modifiedTime")),
        is_folder=f.get("mimeType") == "application/vnd.google-apps.folder",
        parent_id=(f.get("parents") or [None])[0], extra=f)


class _Contacts:
    def __init__(self, account: str | None):
        self._a = account

    def list_contacts(self):
        svc = google_auth.service("people", "v1", account=self._a)
        r = svc.people().connections().list(
            resourceName="people/me", pageSize=1000,
            personFields="names,emailAddresses,phoneNumbers").execute()
        return [_contact(p) for p in r.get("connections", [])]


def _contact(p: dict[str, Any]) -> Contact:
    names = p.get("names", [])
    return Contact(
        id=p.get("resourceName", ""),
        name=names[0].get("displayName", "") if names else "",
        emails=[e.get("value", "") for e in p.get("emailAddresses", [])],
        phones=[n.get("value", "") for n in p.get("phoneNumbers", [])],
        extra=p)


class GoogleProvider(Provider):
    name = "google"
    capabilities = {"mail": True, "calendar": True, "files": True,
                    "contacts": True, "labels": True}

    def __init__(self, account: str | None = None):
        self.account = account

    def mail(self):
        return _Mail(self.account)

    def calendar(self):
        return _Calendar(self.account)

    def files(self):
        return _Files(self.account)

    def contacts(self):
        return _Contacts(self.account)
