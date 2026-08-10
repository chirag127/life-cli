"""Microsoft provider — Graph SDK (msgraph-sdk) + azure-identity, official SDK only.

Graph client is async; each method drives it with asyncio.run and maps Graph
models to canonical dataclasses. SDK + credential imported lazily so importing
this module (and the registry) never requires the Graph SDK be installed.

Env: MS_CLIENT_ID, MS_TENANT_ID (default "common"). Delegated device-code flow.
"""
from __future__ import annotations

import asyncio
import os
from typing import Any

from life_cli.core.models import CalendarEvent, Contact, DriveFile, Message
from life_cli.core.provider import Provider

_SCOPES = ["Mail.ReadWrite", "Mail.Send", "Calendars.ReadWrite",
           "Files.ReadWrite", "Contacts.Read"]


def _run(coro):
    return asyncio.run(coro)


def _client(account: str | None):
    from azure.identity import DeviceCodeCredential
    from msgraph import GraphServiceClient

    cred = DeviceCodeCredential(
        client_id=os.environ["MS_CLIENT_ID"],
        tenant_id=os.environ.get("MS_TENANT_ID", "common"))
    return GraphServiceClient(credentials=cred, scopes=_SCOPES)


def _msg(m: Any) -> Message:
    frm = getattr(getattr(m, "from_", None), "email_address", None)
    return Message(
        id=m.id, thread_id=getattr(m, "conversation_id", None),
        sender=getattr(frm, "address", "") or "",
        to=[r.email_address.address for r in (m.to_recipients or [])
            if r.email_address],
        subject=m.subject or "", snippet=m.body_preview or "",
        body=getattr(m.body, "content", None) if m.body else None,
        date=getattr(m, "received_date_time", None),
        folder=getattr(m, "parent_folder_id", None),
        unread=not bool(getattr(m, "is_read", True)),
        has_attachments=bool(getattr(m, "has_attachments", False)))


def _event(e: Any) -> CalendarEvent:
    return CalendarEvent(
        id=e.id, summary=e.subject or "",
        start=getattr(e.start, "date_time", None),
        end=getattr(e.end, "date_time", None),
        description=getattr(e.body, "content", "") if e.body else "",
        location=getattr(e.location, "display_name", "") if e.location else "",
        attendees=[a.email_address.address for a in (e.attendees or [])
                   if a.email_address])


def _file(d: Any) -> DriveFile:
    return DriveFile(
        id=d.id, name=d.name or "", size=d.size,
        mime_type=getattr(getattr(d, "file", None), "mime_type", "") or "",
        modified=getattr(d, "last_modified_date_time", None),
        is_folder=getattr(d, "folder", None) is not None,
        parent_id=getattr(getattr(d, "parent_reference", None), "id", None))


def _contact(c: Any) -> Contact:
    return Contact(
        id=c.id, name=c.display_name or "",
        emails=[e.address for e in (c.email_addresses or []) if e.address],
        phones=list(c.mobile_phone and [c.mobile_phone] or []) +
               list(c.business_phones or []))


class _Mail:
    def __init__(self, client):
        self._c = client

    def send(self, to, subject, body, attachments=None):
        from msgraph.generated.models.body_type import BodyType
        from msgraph.generated.models.email_address import EmailAddress
        from msgraph.generated.models.item_body import ItemBody
        from msgraph.generated.models.message import Message as GMessage
        from msgraph.generated.models.recipient import Recipient
        from msgraph.generated.users.item.send_mail.send_mail_post_request_body import (
            SendMailPostRequestBody)

        req = SendMailPostRequestBody(
            message=GMessage(
                subject=subject,
                body=ItemBody(content_type=BodyType.Text, content=body),
                to_recipients=[Recipient(email_address=EmailAddress(address=to))]),
            save_to_sent_items=True)
        _run(self._c.me.send_mail.post(req))
        return ""

    def search(self, query, max_results=50):
        r = _run(self._c.me.messages.get())
        return [_msg(m) for m in (getattr(r, "value", None) or [])][:max_results]

    def list_inbox(self, page_size=50):
        r = _run(self._c.me.messages.get())
        return [_msg(m) for m in (getattr(r, "value", None) or [])][:page_size]

    def read(self, msg_id):
        return _msg(_run(self._c.me.messages.by_message_id(msg_id).get()))

    def download_attachments(self, msg_id, out_dir):
        raise NotImplementedError("microsoft attachment download not implemented")


class _Calendar:
    def __init__(self, client):
        self._c = client

    def list_events(self, time_min=None, time_max=None, max_results=50):
        r = _run(self._c.me.events.get())
        return [_event(e) for e in (getattr(r, "value", None) or [])][:max_results]

    def create_event(self, ev: CalendarEvent):
        from msgraph.generated.models.attendee import Attendee
        from msgraph.generated.models.date_time_time_zone import DateTimeTimeZone
        from msgraph.generated.models.email_address import EmailAddress
        from msgraph.generated.models.event import Event
        from msgraph.generated.models.item_body import ItemBody

        e = Event(
            subject=ev.summary,
            body=ItemBody(content=ev.description),
            start=DateTimeTimeZone(date_time=ev.start.isoformat(), time_zone="UTC"),
            end=DateTimeTimeZone(date_time=ev.end.isoformat(), time_zone="UTC"),
            attendees=[Attendee(email_address=EmailAddress(address=a))
                       for a in ev.attendees])
        created = _run(self._c.me.events.post(e))
        return created.id

    def update_event(self, event_id, **fields):
        from msgraph.generated.models.event import Event
        _run(self._c.me.events.by_event_id(event_id).patch(Event(**fields)))

    def delete_event(self, event_id):
        _run(self._c.me.events.by_event_id(event_id).delete())


class _Files:
    def __init__(self, client):
        self._c = client

    def list_files(self, query=None):
        r = _run(self._c.me.drive.root.children.get())
        return [_file(d) for d in (getattr(r, "value", None) or [])]

    def download(self, file_id, dest_path):
        data = _run(self._c.me.drive.items.by_drive_item_id(file_id).content.get())
        with open(dest_path, "wb") as fh:
            fh.write(data)
        return dest_path

    def upload(self, local_path, folder_id=None):
        with open(local_path, "rb") as fh:
            data = fh.read()
        item = _run(self._c.me.drive.items.by_drive_item_id(
            folder_id or "root").content.put(data))
        return item.id

    def delete(self, file_id):
        _run(self._c.me.drive.items.by_drive_item_id(file_id).delete())


class _Contacts:
    def __init__(self, client):
        self._c = client

    def list_contacts(self):
        r = _run(self._c.me.contacts.get())
        return [_contact(c) for c in (getattr(r, "value", None) or [])]


class MicrosoftProvider(Provider):
    name = "microsoft"
    capabilities = {"mail": True, "calendar": True, "files": True,
                    "contacts": True, "labels": False}

    def __init__(self, account: str | None = None):
        self.account = account
        self._client = None

    def _c(self):
        if self._client is None:
            self._client = _client(self.account)
        return self._client

    def mail(self):
        return _Mail(self._c())

    def calendar(self):
        return _Calendar(self._c())

    def files(self):
        return _Files(self._c())

    def contacts(self):
        return _Contacts(self._c())
