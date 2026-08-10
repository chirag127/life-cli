"""MicrosoftProvider — official msgraph-sdk + azure-identity, canonical protocol.

Delegated auth (personal Outlook.com + M365) via InteractiveBrowserCredential.
Per-account token cache: MSAL cache is OS-persisted + isolated by name
(`msgraph-<account>`); the AuthenticationRecord that selects the account is
serialized to config/ms-token-<account>.json for silent re-auth.

msgraph-sdk is async; every public method here is a sync wrapper (asyncio.run)
so the CLI stays synchronous. Native Graph objects are mapped to core.models.

.env:
    MICROSOFT_CLIENT_ID=<Azure app (public client) id>
    MICROSOFT_TENANT_ID=common          # 'common' = personal + work/school
    MICROSOFT_ACCOUNT=personal
"""
from __future__ import annotations

import asyncio
import os
from datetime import datetime
from pathlib import Path

from gsuite_agent.core.models import CalendarEvent, Contact, DriveFile, Message
from gsuite_agent.core.provider import Provider

SCOPES = [
    "Mail.ReadWrite",
    "Mail.Send",
    "Calendars.ReadWrite",
    "Files.ReadWrite.All",
    "Contacts.Read",
    "User.Read",
]

_CFG = Path(__file__).resolve().parent.parent.parent / "config"


def _run(coro):
    return asyncio.run(coro)


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _to_dt(dtz) -> datetime | None:
    return _parse_iso(getattr(dtz, "date_time", None)) if dtz else None


# ---- auth ----

def _record_file(account: str) -> Path:
    return _CFG / f"ms-token-{account}.json"


def _credential(account: str):
    from azure.identity import (
        AuthenticationRecord,
        InteractiveBrowserCredential,
        TokenCachePersistenceOptions,
    )

    cache = TokenCachePersistenceOptions(
        name=f"msgraph-{account}", allow_unencrypted_storage=True)
    kw = {
        "client_id": os.environ.get("MICROSOFT_CLIENT_ID"),
        "tenant_id": os.environ.get("MICROSOFT_TENANT_ID", "common"),
        "cache_persistence_options": cache,
    }
    rec = _record_file(account)
    if rec.exists():
        kw["authentication_record"] = AuthenticationRecord.deserialize(
            rec.read_text(encoding="utf-8"))
        return InteractiveBrowserCredential(**kw)

    cred = InteractiveBrowserCredential(**kw)
    record = cred.authenticate(scopes=SCOPES)
    _CFG.mkdir(parents=True, exist_ok=True)
    rec.write_text(record.serialize(), encoding="utf-8")
    return cred


def _client(account: str):
    from msgraph import GraphServiceClient

    return GraphServiceClient(credentials=_credential(account), scopes=SCOPES)


# ---- adapters: native -> canonical ----

def _to_message(m) -> Message:
    frm = getattr(getattr(m, "from_escaped", None), "email_address", None)
    body = getattr(m, "body", None)
    return Message(
        id=m.id, thread_id=getattr(m, "conversation_id", None),
        sender=getattr(frm, "address", "") or "",
        to=[r.email_address.address for r in (m.to_recipients or [])
            if r.email_address and r.email_address.address],
        subject=m.subject or "",
        snippet=getattr(m, "body_preview", "") or "",
        body=getattr(body, "content", None),
        date=_parse_iso(str(m.received_date_time)) if m.received_date_time else None,
        folder=getattr(m, "parent_folder_id", None),
        unread=not (m.is_read if m.is_read is not None else True),
        has_attachments=bool(m.has_attachments),
        extra={"webLink": getattr(m, "web_link", None)},
    )


def _to_event(e) -> CalendarEvent:
    loc = getattr(getattr(e, "location", None), "display_name", "") or ""
    return CalendarEvent(
        id=e.id, summary=e.subject or "",
        start=_to_dt(e.start) or datetime.min, end=_to_dt(e.end) or datetime.min,
        description=getattr(getattr(e, "body", None), "content", "") or "",
        location=loc,
        attendees=[a.email_address.address for a in (e.attendees or [])
                   if a.email_address and a.email_address.address],
        extra={"webLink": getattr(e, "web_link", None)},
    )


def _to_file(f) -> DriveFile:
    return DriveFile(
        id=f.id, name=f.name or "", mime_type=_file_mime(f),
        size=f.size,
        modified=_parse_iso(str(f.last_modified_date_time))
        if f.last_modified_date_time else None,
        is_folder=f.folder is not None,
        parent_id=getattr(getattr(f, "parent_reference", None), "id", None),
        extra={"webUrl": getattr(f, "web_url", None)},
    )


def _file_mime(f) -> str:
    if f.folder is not None:
        return "application/vnd.microsoft.folder"
    return getattr(getattr(f, "file", None), "mime_type", "") or ""


def _to_contact(c) -> Contact:
    name = c.display_name or " ".join(
        x for x in [getattr(c, "given_name", None), getattr(c, "surname", None)] if x)
    return Contact(
        id=c.id, name=name or "",
        emails=[e.address for e in (c.email_addresses or []) if e.address],
        phones=list(c.mobile_phone and [c.mobile_phone] or []) + list(
            c.business_phones or []) + list(c.home_phones or []),
    )


# ---- sub-providers ----

class _Mail:
    def __init__(self, client):
        self._c = client

    def send(self, to: str, subject: str, body: str,
             attachments: list[str] | None = None) -> str:
        _run(self._send(to, subject, body, attachments))
        return ""

    async def _send(self, to, subject, body, attachments):
        import base64
        import mimetypes

        from msgraph.generated.models.body_type import BodyType
        from msgraph.generated.models.email_address import EmailAddress
        from msgraph.generated.models.file_attachment import FileAttachment
        from msgraph.generated.models.importance import Importance  # noqa: F401
        from msgraph.generated.models.item_body import ItemBody
        from msgraph.generated.models.message import Message as GMessage
        from msgraph.generated.models.recipient import Recipient
        from msgraph.generated.users.item.send_mail.send_mail_post_request_body import (
            SendMailPostRequestBody,
        )

        recipients = []
        for addr in [a.strip() for a in to.split(",") if a.strip()]:
            ea = EmailAddress()
            ea.address = addr
            r = Recipient()
            r.email_address = ea
            recipients.append(r)

        item = ItemBody()
        item.content = body
        item.content_type = BodyType.Text

        msg = GMessage()
        msg.subject = subject
        msg.body = item
        msg.to_recipients = recipients
        msg.attachments = []
        for path in attachments or []:
            p = Path(path)
            att = FileAttachment()
            att.odata_type = "#microsoft.graph.fileAttachment"
            att.name = p.name
            att.content_type = mimetypes.guess_type(path)[0] or "application/octet-stream"
            att.content_bytes = base64.b64encode(p.read_bytes())
            msg.attachments.append(att)

        req = SendMailPostRequestBody()
        req.message = msg
        req.save_to_sent_items = True
        await self._c.me.send_mail.post(req)

    def search(self, query: str, max_results: int = 50) -> list[Message]:
        return _run(self._list(search=query, top=max_results))

    def list_inbox(self, page_size: int = 50) -> list[Message]:
        return _run(self._list(top=page_size))

    async def _list(self, search=None, top=50):
        from msgraph.generated.users.item.messages.messages_request_builder import (
            MessagesRequestBuilder,
        )

        qp = MessagesRequestBuilder.MessagesRequestBuilderGetQueryParameters(top=top)
        if search:
            qp.search = f'"{search}"'
        else:
            qp.orderby = ["receivedDateTime desc"]
        cfg = MessagesRequestBuilder.MessagesRequestBuilderGetRequestConfiguration(
            query_parameters=qp)
        page = await self._c.me.messages.get(request_configuration=cfg)
        return [_to_message(m) for m in (page.value if page else [])]

    def read(self, msg_id: str) -> Message:
        return _run(self._read(msg_id))

    async def _read(self, msg_id):
        m = await self._c.me.messages.by_message_id(msg_id).get()
        return _to_message(m)

    def download_attachments(self, msg_id: str, out_dir: str) -> list[str]:
        return _run(self._download(msg_id, out_dir))

    async def _download(self, msg_id, out_dir):
        import base64

        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        page = await self._c.me.messages.by_message_id(msg_id).attachments.get()
        saved = []
        for att in (page.value if page else []):
            data = getattr(att, "content_bytes", None)
            name = getattr(att, "name", None)
            if data and name:
                dest = out / name
                dest.write_bytes(base64.b64decode(data))
                saved.append(str(dest))
        return saved


class _Calendar:
    def __init__(self, client):
        self._c = client

    def list_events(self, time_min=None, time_max=None,
                    max_results: int = 50) -> list[CalendarEvent]:
        return _run(self._list(max_results))

    async def _list(self, top):
        from msgraph.generated.users.item.events.events_request_builder import (
            EventsRequestBuilder,
        )

        qp = EventsRequestBuilder.EventsRequestBuilderGetQueryParameters(
            top=top, orderby=["start/dateTime"])
        cfg = EventsRequestBuilder.EventsRequestBuilderGetRequestConfiguration(
            query_parameters=qp)
        page = await self._c.me.events.get(request_configuration=cfg)
        return [_to_event(e) for e in (page.value if page else [])]

    def create_event(self, ev: CalendarEvent) -> str:
        return _run(self._create(ev))

    async def _create(self, ev):
        from msgraph.generated.models.attendee import Attendee
        from msgraph.generated.models.date_time_time_zone import DateTimeTimeZone
        from msgraph.generated.models.email_address import EmailAddress
        from msgraph.generated.models.event import Event
        from msgraph.generated.models.item_body import ItemBody
        from msgraph.generated.models.location import Location

        e = Event()
        e.subject = ev.summary
        e.start = _dttz(ev.start)
        e.end = _dttz(ev.end)
        if ev.description:
            body = ItemBody()
            body.content = ev.description
            e.body = body
        if ev.location:
            loc = Location()
            loc.display_name = ev.location
            e.location = loc
        attendees = []
        for addr in ev.attendees or []:
            ea = EmailAddress()
            ea.address = addr
            a = Attendee()
            a.email_address = ea
            attendees.append(a)
        e.attendees = attendees
        created = await self._c.me.events.post(e)
        return created.id if created else ""

    def update_event(self, event_id: str, **fields) -> None:
        _run(self._update(event_id, fields))

    async def _update(self, event_id, fields):
        from msgraph.generated.models.event import Event
        from msgraph.generated.models.item_body import ItemBody

        e = Event()
        if "summary" in fields:
            e.subject = fields["summary"]
        if "start" in fields:
            e.start = _dttz(fields["start"])
        if "end" in fields:
            e.end = _dttz(fields["end"])
        if "description" in fields:
            body = ItemBody()
            body.content = fields["description"]
            e.body = body
        await self._c.me.events.by_event_id(event_id).patch(e)

    def delete_event(self, event_id: str) -> None:
        _run(self._c.me.events.by_event_id(event_id).delete())


def _dttz(dt: datetime):
    from msgraph.generated.models.date_time_time_zone import DateTimeTimeZone

    z = DateTimeTimeZone()
    z.date_time = dt.isoformat()
    z.time_zone = "UTC"
    return z


class _Files:
    def __init__(self, client):
        self._c = client

    def list_files(self, query: str | None = None) -> list[DriveFile]:
        return _run(self._list(query))

    async def _list(self, query):
        drive = await self._c.me.drive.get()
        items_rb = self._c.drives.by_drive_id(drive.id).items
        if query:
            page = await items_rb.by_drive_item_id("root").search_with_q(query).get()
        else:
            page = await items_rb.by_drive_item_id("root").children.get()
        return [_to_file(f) for f in (page.value if page else [])]

    def download(self, file_id: str, dest_path: str) -> str:
        return _run(self._download(file_id, dest_path))

    async def _download(self, file_id, dest_path):
        drive = await self._c.me.drive.get()
        content = await self._c.drives.by_drive_id(drive.id).items.by_drive_item_id(
            file_id).content.get()
        Path(dest_path).write_bytes(content)
        return dest_path

    def upload(self, local_path: str, folder_id: str | None = None) -> str:
        return _run(self._upload(local_path, folder_id))

    async def _upload(self, local_path, folder_id):
        p = Path(local_path)
        drive = await self._c.me.drive.get()
        items = self._c.drives.by_drive_id(drive.id).items
        item_path = f"{folder_id}:/{p.name}:" if folder_id else f"root:/{p.name}:"
        uploaded = await items.by_drive_item_id(item_path).content.put(p.read_bytes())
        return uploaded.id if uploaded else ""

    def delete(self, file_id: str) -> None:
        _run(self._delete(file_id))

    async def _delete(self, file_id):
        drive = await self._c.me.drive.get()
        await self._c.drives.by_drive_id(drive.id).items.by_drive_item_id(
            file_id).delete()


class _Contacts:
    def __init__(self, client):
        self._c = client

    def list_contacts(self) -> list[Contact]:
        return _run(self._list())

    async def _list(self):
        page = await self._c.me.contacts.get()
        return [_to_contact(c) for c in (page.value if page else [])]


class MicrosoftProvider(Provider):
    name = "microsoft"
    capabilities = {"mail": True, "calendar": True, "files": True,
                    "contacts": True, "folders": True}

    def __init__(self, account: str | None = None):
        self.account = account or os.environ.get("MICROSOFT_ACCOUNT", "default")
        self._client_obj = None

    def _client(self):
        if self._client_obj is None:
            self._client_obj = _client(self.account)
        return self._client_obj

    def mail(self) -> _Mail:
        return _Mail(self._client())

    def calendar(self) -> _Calendar:
        return _Calendar(self._client())

    def files(self) -> _Files:
        return _Files(self._client())

    def contacts(self) -> _Contacts:
        return _Contacts(self._client())
