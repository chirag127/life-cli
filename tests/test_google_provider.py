from datetime import datetime

from gsuite_agent.core.models import CalendarEvent
from gsuite_agent.providers import google_provider as gp
from gsuite_agent.providers.google_provider import GoogleProvider


def test_capabilities():
    assert GoogleProvider().capabilities["mail"] is True
    assert GoogleProvider().capabilities["labels"] is True


# ---- mail ----

def test_mail_send_threads_account(monkeypatch):
    seen = {}
    monkeypatch.setattr(gp.gmail_api, "send",
                        lambda to, s, b, a, account: seen.update(
                            to=to, account=account) or "ID1")
    out = GoogleProvider("why").mail().send("t@x.com", "S", "B")
    assert out == "ID1"
    assert seen == {"to": "t@x.com", "account": "why"}


def test_mail_search_maps_to_message(monkeypatch):
    monkeypatch.setattr(gp.gmail_api, "search", lambda q, n, account: [
        {"id": "m1", "from": "a@x.com", "subject": "Hi", "snippet": "s"}])
    msgs = GoogleProvider().mail().search("q")
    assert msgs[0].id == "m1"
    assert msgs[0].sender == "a@x.com"
    assert msgs[0].subject == "Hi"


def test_mail_read_parses_headers(monkeypatch):
    monkeypatch.setattr(gp.gmail_api, "read", lambda mid, account: {
        "id": mid, "threadId": "t1", "snippet": "sn",
        "labelIds": ["INBOX", "UNREAD"],
        "payload": {"headers": [
            {"name": "From", "value": "a@x.com"},
            {"name": "To", "value": "b@x.com,c@x.com"},
            {"name": "Subject", "value": "Re"},
        ]}})
    m = GoogleProvider().mail().read("m9")
    assert m.sender == "a@x.com"
    assert m.to == ["b@x.com", "c@x.com"]
    assert m.unread is True
    assert m.thread_id == "t1"


# ---- calendar ----

def test_calendar_list_maps_event(monkeypatch):
    monkeypatch.setattr(gp.gcal, "list_events", lambda **kw: [{
        "id": "e1", "summary": "Mtg",
        "start": {"dateTime": "2026-01-01T10:00:00+00:00"},
        "end": {"dateTime": "2026-01-01T11:00:00+00:00"},
        "attendees": [{"email": "x@x.com"}]}])
    ev = GoogleProvider().calendar().list_events()[0]
    assert ev.id == "e1"
    assert ev.summary == "Mtg"
    assert ev.attendees == ["x@x.com"]
    assert ev.start.hour == 10


def test_calendar_create_passes_iso(monkeypatch):
    captured = {}
    monkeypatch.setattr(gp.gcal, "create_event",
                        lambda summary, s, e, **kw: captured.update(
                            summary=summary, start=s, end=e, kw=kw) or "E1")
    ev = CalendarEvent(id="", summary="X",
                       start=datetime(2026, 1, 1, 9),
                       end=datetime(2026, 1, 1, 10), attendees=["a@x.com"])
    assert GoogleProvider("chirag").calendar().create_event(ev) == "E1"
    assert captured["start"] == "2026-01-01T09:00:00"
    assert captured["kw"]["account"] == "chirag"


def test_calendar_delete_threads_account(monkeypatch):
    seen = {}
    monkeypatch.setattr(gp.gcal, "delete_event",
                        lambda eid, account: seen.update(eid=eid, account=account))
    GoogleProvider("why").calendar().delete_event("e5")
    assert seen == {"eid": "e5", "account": "why"}


# ---- files ----

def test_files_list_maps_drivefile(monkeypatch):
    monkeypatch.setattr(gp.gdrive, "list_files", lambda query, account: [{
        "id": "f1", "name": "doc.pdf", "mimeType": "application/pdf",
        "size": "1024", "parents": ["p1"]}])
    f = GoogleProvider().files().list_files()[0]
    assert f.id == "f1"
    assert f.size == 1024
    assert f.is_folder is False
    assert f.parent_id == "p1"


def test_files_folder_flag(monkeypatch):
    monkeypatch.setattr(gp.gdrive, "list_files", lambda query, account: [{
        "id": "d1", "name": "dir",
        "mimeType": "application/vnd.google-apps.folder"}])
    f = GoogleProvider().files().list_files()[0]
    assert f.is_folder is True
    assert f.size is None


def test_files_upload_threads_account(monkeypatch):
    seen = {}
    monkeypatch.setattr(gp.gdrive, "upload",
                        lambda lp, folder_id, account: seen.update(
                            lp=lp, folder_id=folder_id, account=account) or "U1")
    assert GoogleProvider("why").files().upload("/tmp/x", "fold") == "U1"
    assert seen == {"lp": "/tmp/x", "folder_id": "fold", "account": "why"}


# ---- contacts ----

def test_contacts_list_maps(monkeypatch):
    class Conn:
        def list(self, **kw):
            class R:
                def execute(self_):
                    return {"connections": [{
                        "resourceName": "people/1",
                        "names": [{"displayName": "Al"}],
                        "emailAddresses": [{"value": "al@x.com"}],
                        "phoneNumbers": [{"value": "123"}]}]}
            return R()

    class People:
        def connections(self):
            return Conn()

    class Svc:
        def people(self):
            return People()

    seen = {}
    monkeypatch.setattr(gp.google_auth, "service",
                        lambda api, v, account: seen.update(
                            api=api, account=account) or Svc())
    c = GoogleProvider("chirag").contacts().list_contacts()[0]
    assert seen == {"api": "people", "account": "chirag"}
    assert c.name == "Al"
    assert c.emails == ["al@x.com"]
    assert c.phones == ["123"]
