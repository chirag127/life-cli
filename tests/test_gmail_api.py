import base64

import pytest

from life_cli import gmail_api


class FakeExec:
    def __init__(self, result):
        self._result = result

    def execute(self):
        return self._result


class FakeAttachments:
    def __init__(self, store):
        self._store = store

    def get(self, userId, messageId, id):
        return FakeExec(self._store[id])


class FakeMessages:
    def __init__(self, svc):
        self._svc = svc

    def send(self, userId, body):
        self._svc.sent.append((userId, body))
        return FakeExec({"id": "SENT1"})

    def list(self, userId, **kw):
        self._svc.calls.append(("list", userId, kw))
        return FakeExec(self._svc.list_result)

    def get(self, userId, id, format=None, metadataHeaders=None):
        self._svc.calls.append(("get", userId, id, format))
        return FakeExec(self._svc.messages_by_id[id])

    def attachments(self):
        return FakeAttachments(self._svc.attachment_data)


class FakeUsers:
    def __init__(self, svc):
        self._svc = svc

    def messages(self):
        return FakeMessages(self._svc)


class FakeService:
    def __init__(self):
        self.sent = []
        self.calls = []
        self.list_result = {"messages": []}
        self.messages_by_id = {}
        self.attachment_data = {}

    def users(self):
        return FakeUsers(self)


@pytest.fixture
def svc(monkeypatch):
    s = FakeService()
    seen = []

    def fake_service(api, version, account=None):
        seen.append((api, version, account))
        return s

    monkeypatch.setattr(gmail_api.google_auth, "service", fake_service)
    s.seen = seen
    return s


def test_service_passes_account(svc):
    gmail_api._service("why")
    assert svc.seen == [("gmail", "v1", "why")]


def test_service_default_account_none(svc):
    gmail_api._service()
    assert svc.seen == [("gmail", "v1", None)]


def test_send_threads_account(svc):
    mid = gmail_api.send("to@x.com", "Subj", "Body", account="chirag")
    assert mid == "SENT1"
    assert svc.seen[0] == ("gmail", "v1", "chirag")
    userId, body = svc.sent[0]
    assert userId == "me"
    decoded = base64.urlsafe_b64decode(body["raw"]).decode()
    assert "To: to@x.com" in decoded
    assert "Subject: Subj" in decoded


def test_send_with_sender_and_attachment(svc, tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("hi")
    gmail_api.send("t@x.com", "S", "B", attachments=[str(f)], sender="me@x.com")
    _, body = svc.sent[0]
    decoded = base64.urlsafe_b64decode(body["raw"]).decode()
    assert "From: me@x.com" in decoded
    assert "a.txt" in decoded


def test_send_default_account_none(svc):
    gmail_api.send("to@x.com", "S", "B")
    assert svc.seen[0][2] is None


def test_search_threads_account_and_parses(svc):
    svc.list_result = {"messages": [{"id": "m1"}]}
    svc.messages_by_id = {"m1": {"payload": {"headers": [
        {"name": "From", "value": "a@x.com"},
        {"name": "Subject", "value": "Hello"},
        {"name": "Date", "value": "Mon"},
    ]}, "snippet": "hi"}}
    out = gmail_api.search("q", max_results=10, account="why")
    assert svc.seen[0] == ("gmail", "v1", "why")
    assert svc.calls[0] == ("list", "me", {"q": "q", "maxResults": 10})
    assert out == [{"id": "m1", "from": "a@x.com", "subject": "Hello",
                    "date": "Mon", "snippet": "hi"}]


def test_search_default_account_none(svc):
    gmail_api.search("q")
    assert svc.seen[0][2] is None


def test_list_inbox_threads_account(svc):
    svc.list_result = {"messages": []}
    gmail_api.list_inbox("SENT", page_size=5, account="chirag")
    assert svc.seen[0] == ("gmail", "v1", "chirag")
    assert svc.calls[0] == ("list", "me", {"labelIds": ["SENT"], "maxResults": 5})


def test_read_threads_account(svc):
    svc.messages_by_id = {"m9": {"id": "m9", "payload": {}}}
    out = gmail_api.read("m9", account="why")
    assert svc.seen[0] == ("gmail", "v1", "why")
    assert svc.calls[0] == ("get", "me", "m9", "full")
    assert out == {"id": "m9", "payload": {}}


def test_download_attachments_threads_account(svc, tmp_path):
    svc.messages_by_id = {"m1": {"payload": {"parts": [
        {"filename": "doc.pdf", "body": {"attachmentId": "att1"}},
    ]}}}
    svc.attachment_data = {"att1": {"data": base64.urlsafe_b64encode(b"PDF").decode()}}
    out = tmp_path / "dl"
    saved = gmail_api.download_attachments("m1", str(out), account="chirag")
    assert svc.seen[0] == ("gmail", "v1", "chirag")
    dest = out / "doc.pdf"
    assert saved == [str(dest)]
    assert dest.read_bytes() == b"PDF"


def test_download_attachments_nested_parts(svc, tmp_path):
    svc.messages_by_id = {"m1": {"payload": {"parts": [
        {"filename": "", "body": {}, "parts": [
            {"filename": "n.txt", "body": {"attachmentId": "att2"}},
        ]},
    ]}}}
    svc.attachment_data = {"att2": {"data": base64.urlsafe_b64encode(b"NEST").decode()}}
    out = tmp_path / "dl"
    saved = gmail_api.download_attachments("m1", str(out))
    assert saved == [str(out / "n.txt")]
    assert svc.seen[0][2] is None
