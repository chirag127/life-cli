import pytest

from life_cli import calendar


class Exec:
    def __init__(self, ret):
        self.ret = ret

    def execute(self):
        return self.ret


class Events:
    def __init__(self, calls):
        self.calls = calls

    def list(self, **kw):
        self.calls.append(("list", kw))
        return Exec({"items": [{"id": "e1"}]})

    def insert(self, **kw):
        self.calls.append(("insert", kw))
        return Exec({"id": "new1"})

    def patch(self, **kw):
        self.calls.append(("patch", kw))
        return Exec({"id": kw.get("eventId"), "updated": True})

    def delete(self, **kw):
        self.calls.append(("delete", kw))
        return Exec(None)


class CalList:
    def __init__(self, calls):
        self.calls = calls

    def list(self, **kw):
        self.calls.append(("calendarList.list", kw))
        return Exec({"items": [{"id": "primary"}]})


class Svc:
    def __init__(self, calls):
        self.calls = calls

    def events(self):
        return Events(self.calls)

    def calendarList(self):
        return CalList(self.calls)


@pytest.fixture
def svc(monkeypatch):
    calls = []
    seen = {}

    def fake_service(api, version, account):
        seen.update(api=api, version=version, account=account)
        return Svc(calls)

    monkeypatch.setattr(calendar.google_auth, "service", fake_service)
    return calls, seen


def test_service_api_version(svc):
    calls, seen = svc
    calendar.list_calendars()
    assert seen == {"api": "calendar", "version": "v3", "account": None}


def test_account_passthrough(svc):
    calls, seen = svc
    calendar.list_events(account="chirag")
    assert seen["account"] == "chirag"


def test_list_events_defaults(svc):
    calls, _ = svc
    assert calendar.list_events() == [{"id": "e1"}]
    op, kw = calls[0]
    assert op == "list"
    assert kw == {"calendarId": "primary", "maxResults": 50,
                  "singleEvents": True, "orderBy": "startTime"}


def test_list_events_time_window(svc):
    calls, _ = svc
    calendar.list_events(calendar_id="c2", time_min="A", time_max="B", max_results=5)
    _, kw = calls[0]
    assert kw["calendarId"] == "c2"
    assert kw["timeMin"] == "A"
    assert kw["timeMax"] == "B"
    assert kw["maxResults"] == 5


def test_list_events_omits_empty_times(svc):
    calls, _ = svc
    calendar.list_events()
    _, kw = calls[0]
    assert "timeMin" not in kw and "timeMax" not in kw


def test_create_event_body_and_id(svc):
    calls, _ = svc
    eid = calendar.create_event("Meet", "2026-01-01T10:00:00Z", "2026-01-01T11:00:00Z",
                                description="d", attendees=["a@x.com", "b@x.com"])
    assert eid == "new1"
    op, kw = calls[0]
    assert op == "insert"
    assert kw["calendarId"] == "primary"
    body = kw["body"]
    assert body["summary"] == "Meet"
    assert body["description"] == "d"
    assert body["start"] == {"dateTime": "2026-01-01T10:00:00Z"}
    assert body["end"] == {"dateTime": "2026-01-01T11:00:00Z"}
    assert body["attendees"] == [{"email": "a@x.com"}, {"email": "b@x.com"}]


def test_create_event_no_attendees_key(svc):
    calls, _ = svc
    calendar.create_event("S", "s", "e")
    _, kw = calls[0]
    assert "attendees" not in kw["body"]


def test_update_event_patches_fields(svc):
    calls, _ = svc
    r = calendar.update_event("e9", summary="New", location="Room")
    assert r["updated"] is True
    op, kw = calls[0]
    assert op == "patch"
    assert kw["eventId"] == "e9"
    assert kw["calendarId"] == "primary"
    assert kw["body"] == {"summary": "New", "location": "Room"}


def test_delete_event(svc):
    calls, _ = svc
    assert calendar.delete_event("e9", calendar_id="c1") is None
    op, kw = calls[0]
    assert op == "delete"
    assert kw == {"calendarId": "c1", "eventId": "e9"}


def test_list_calendars(svc):
    calls, _ = svc
    assert calendar.list_calendars() == [{"id": "primary"}]
    assert calls[0][0] == "calendarList.list"
