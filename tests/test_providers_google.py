from datetime import datetime, timezone

import pytest

from gsuite_agent.core.models import CalendarEvent, Contact, DriveFile, Message
from gsuite_agent.core.provider import (
    CalendarProvider,
    ContactProvider,
    FileProvider,
    MailProvider,
    Provider,
)
from gsuite_agent.providers import google as gp


@pytest.fixture
def prov():
    return gp.GoogleProvider(account="why")


def test_identity_and_capabilities(prov):
    assert prov.name == "google"
    assert prov.capabilities == {"mail": True, "calendar": True, "files": True,
                                 "contacts": True, "labels": True}
    assert isinstance(prov, Provider)


def test_subproviders_match_protocols(prov):
    assert isinstance(prov.mail(), MailProvider)
    assert isinstance(prov.calendar(), CalendarProvider)
    assert isinstance(prov.files(), FileProvider)
    assert isinstance(prov.contacts(), ContactProvider)


# ---- mail ----

def test_mail_send_threads_account(monkeypatch, prov):
    calls = {}

    def fake_send(*a, **k):
        calls["v"] = (a, k)
        return "ID1"

    monkeypatch.setattr(gp.gmail_api, "send", fake_send)
    assert prov.mail().send("t@x.com", "S", "B", ["f.txt"]) == "ID1"
    assert calls["v"] == (("t@x.com", "S", "B", ["f.txt"]), {"account": "why"})


def test_mail_search_converts(monkeypatch, prov):
    monkeypatch.setattr(gp.gmail_api, "search", lambda q, m, account=None: [
        {"id": "m1", "from": "a@x.com", "subject": "Hi", "date": "Mon, 01 Jan 2024 00:00:00 +0000", "snippet": "s"},
    ])
    out = prov.mail().search("q", max_results=5)
    assert len(out) == 1 and isinstance(out[0], Message)
    assert out[0].id == "m1" and out[0].sender == "a@x.com"
    assert out[0].subject == "Hi" and out[0].date.year == 2024


def test_mail_list_inbox_converts(monkeypatch, prov):
    monkeypatch.setattr(gp.gmail_api, "list_inbox", lambda page_size, account=None: [
        {"id": "m2", "from": "b@x.com", "subject": "Yo", "date": "", "snippet": ""},
    ])
    out = prov.mail().list_inbox(page_size=10)
    assert out[0].id == "m2" and out[0].date is None


def test_mail_read_full_message(monkeypatch, prov):
    import base64
    body = base64.urlsafe_b64encode(b"hello body").decode()
    monkeypatch.setattr(gp.gmail_api, "read", lambda mid, account=None: {
        "id": "m9", "threadId": "t9", "snippet": "sn", "labelIds": ["INBOX", "UNREAD"],
        "payload": {"headers": [
            {"name": "From", "value": "s@x.com"},
            {"name": "To", "value": "a@x.com, b@x.com"},
            {"name": "Subject", "value": "Subj"},
            {"name": "Date", "value": "Mon, 01 Jan 2024 00:00:00 +0000"},
        ], "parts": [
            {"mimeType": "text/plain", "body": {"data": body}},
            {"filename": "doc.pdf", "body": {"attachmentId": "att1"}},
        ]},
    })
    msg = prov.mail().read("m9")
    assert msg.thread_id == "t9" and msg.to == ["a@x.com", "b@x.com"]
    assert msg.body == "hello body" and msg.unread is True
    assert msg.folder == "INBOX" and msg.has_attachments is True


def test_mail_download_attachments_delegates(monkeypatch, prov):
    monkeypatch.setattr(gp.gmail_api, "download_attachments",
                        lambda mid, out, account=None: [f"{out}/x", account])
    assert prov.mail().download_attachments("m1", "/tmp/d") == ["/tmp/d/x", "why"]


# ---- calendar ----

def test_calendar_list_converts(monkeypatch, prov):
    monkeypatch.setattr(gp.calendar_mod, "list_events", lambda **k: [{
        "id": "e1", "summary": "Meet",
        "start": {"dateTime": "2024-01-02T10:00:00+00:00"},
        "end": {"dateTime": "2024-01-02T11:00:00+00:00"},
        "attendees": [{"email": "a@x.com"}], "location": "Room",
    }])
    out = prov.calendar().list_events(max_results=5)
    assert isinstance(out[0], CalendarEvent)
    assert out[0].summary == "Meet" and out[0].attendees == ["a@x.com"]
    assert out[0].start.hour == 10


def test_calendar_create_maps_fields(monkeypatch, prov):
    seen = {}
    monkeypatch.setattr(gp.calendar_mod, "create_event",
                        lambda *a, **k: seen.update(a=a, k=k) or "EV1")
    ev = CalendarEvent(id="", summary="S",
                       start=datetime(2024, 1, 1, 9, tzinfo=timezone.utc),
                       end=datetime(2024, 1, 1, 10, tzinfo=timezone.utc),
                       description="d", attendees=["a@x.com"], calendar_id="c1")
    assert prov.calendar().create_event(ev) == "EV1"
    assert seen["a"][0] == "S"
    assert seen["k"] == {"description": "d", "attendees": ["a@x.com"],
                         "calendar_id": "c1", "account": "why"}


def test_calendar_update_delete_thread_account(monkeypatch, prov):
    seen = {}
    monkeypatch.setattr(gp.calendar_mod, "update_event",
                        lambda eid, account=None, **f: seen.update(u=(eid, account, f)))
    monkeypatch.setattr(gp.calendar_mod, "delete_event",
                        lambda eid, account=None: seen.update(d=(eid, account)))
    prov.calendar().update_event("e1", summary="x")
    prov.calendar().delete_event("e1")
    assert seen["u"] == ("e1", "why", {"summary": "x"})
    assert seen["d"] == ("e1", "why")


# ---- files ----

def test_files_list_converts(monkeypatch, prov):
    monkeypatch.setattr(gp.drive_mod, "list_files", lambda query=None, account=None: [{
        "id": "f1", "name": "n", "mimeType": "text/plain", "size": "12",
        "modifiedTime": "2024-01-01T00:00:00Z", "parents": ["p1"],
    }, {
        "id": "d1", "name": "dir", "mimeType": "application/vnd.google-apps.folder",
    }])
    out = prov.files().list_files()
    assert isinstance(out[0], DriveFile)
    assert out[0].size == 12 and out[0].parent_id == "p1" and out[0].is_folder is False
    assert out[1].is_folder is True and out[1].size is None


def test_files_transfer_delegates(monkeypatch, prov):
    seen = {}
    monkeypatch.setattr(gp.drive_mod, "download",
                        lambda fid, dest, account=None: seen.update(dl=(fid, dest, account)) or dest)
    monkeypatch.setattr(gp.drive_mod, "upload",
                        lambda lp, folder_id=None, account=None: seen.update(up=(lp, folder_id, account)) or "U1")
    monkeypatch.setattr(gp.drive_mod, "delete",
                        lambda fid, account=None: seen.update(rm=(fid, account)))
    assert prov.files().download("f1", "/o") == "/o"
    assert prov.files().upload("/l", "fold") == "U1"
    prov.files().delete("f1")
    assert seen["dl"] == ("f1", "/o", "why")
    assert seen["up"] == ("/l", "fold", "why")
    assert seen["rm"] == ("f1", "why")


# ---- contacts ----

def test_contacts_converts(monkeypatch, prov):
    monkeypatch.setattr(gp.contacts_mod, "list_contacts", lambda account=None: [{
        "resourceName": "people/c1",
        "names": [{"displayName": "Ann"}],
        "emailAddresses": [{"value": "ann@x.com"}],
        "phoneNumbers": [{"value": "123"}],
    }])
    out = prov.contacts().list_contacts()
    assert isinstance(out[0], Contact)
    assert out[0].id == "people/c1" and out[0].name == "Ann"
    assert out[0].emails == ["ann@x.com"] and out[0].phones == ["123"]


def test_default_account_none():
    assert gp.GoogleProvider()._account is None
