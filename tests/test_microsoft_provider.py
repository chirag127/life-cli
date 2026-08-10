"""Microsoft adapter tests — fake async Graph client injected via _client, so
the real msgraph-sdk/azure-identity are never imported. Proves the registry and
this module import without the SDKs present, and that Graph models map to
canonical dataclasses.
"""
from types import SimpleNamespace

import pytest

from life_cli.providers import microsoft_provider as mp
from life_cli.providers.microsoft_provider import MicrosoftProvider


def _async(value):
    async def _coro(*a, **k):
        return value
    return _coro


class FakeGetter:
    def __init__(self, value):
        self.get = _async(value)


class FakeItem:
    def __init__(self, value):
        self.get = _async(value)
        self.delete = _async(None)


def make_client(*, messages=None, events=None, files=None, contacts=None,
                one_message=None):
    me = SimpleNamespace()
    me.messages = FakeGetter(SimpleNamespace(value=messages or []))
    me.messages.by_message_id = lambda mid: FakeItem(one_message)
    me.events = FakeGetter(SimpleNamespace(value=events or []))
    me.events.by_event_id = lambda eid: FakeItem(None)
    root = SimpleNamespace(children=FakeGetter(SimpleNamespace(value=files or [])))
    me.drive = SimpleNamespace(root=root)
    me.contacts = FakeGetter(SimpleNamespace(value=contacts or []))
    return SimpleNamespace(me=me)


@pytest.fixture
def provider(monkeypatch):
    client = make_client()

    def _c(prov):
        provider._client_built = True
        return client

    provider._client_built = False
    provider._client = client
    monkeypatch.setattr(mp, "_client", _c)
    return provider


def test_registry_imports_without_sdk():
    # importing the registry + this module must not require msgraph/azure
    from life_cli.providers.registry import get_provider
    assert get_provider("microsoft").name == "microsoft"


def test_capabilities():
    caps = MicrosoftProvider().capabilities
    assert caps["mail"] is True
    assert caps["labels"] is False


def test_client_lazy(monkeypatch):
    calls = []
    monkeypatch.setattr(mp, "_client", lambda p: calls.append(1) or object())
    prov = MicrosoftProvider()
    assert calls == []          # constructing does not build client
    prov._c()
    prov._c()
    assert calls == [1]         # built once, cached


def test_mail_search_maps(provider):
    gmsg = SimpleNamespace(
        id="m1", conversation_id="c1", subject="Hi", body_preview="prev",
        body=SimpleNamespace(content="full"),
        from_=SimpleNamespace(email_address=SimpleNamespace(address="a@x.com")),
        to_recipients=[SimpleNamespace(
            email_address=SimpleNamespace(address="b@x.com"))],
        received_date_time=None, parent_folder_id="inbox",
        is_read=False, has_attachments=True)
    prov = MicrosoftProvider()
    prov._client = make_client(messages=[gmsg])
    msgs = prov.mail().search("q")
    assert msgs[0].id == "m1"
    assert msgs[0].sender == "a@x.com"
    assert msgs[0].to == ["b@x.com"]
    assert msgs[0].unread is True
    assert msgs[0].has_attachments is True


def test_mail_read_maps(provider):
    gmsg = SimpleNamespace(
        id="m9", conversation_id=None, subject="Re", body_preview="p",
        body=None, from_=None, to_recipients=[],
        received_date_time=None, parent_folder_id=None,
        is_read=True, has_attachments=False)
    prov = MicrosoftProvider()
    prov._client = make_client(one_message=gmsg)
    m = prov.mail().read("m9")
    assert m.id == "m9"
    assert m.sender == ""
    assert m.unread is False


def test_calendar_list_maps(provider):
    ev = SimpleNamespace(
        id="e1", subject="Mtg",
        start=SimpleNamespace(date_time="2026-01-01T10:00:00"),
        end=SimpleNamespace(date_time="2026-01-01T11:00:00"),
        body=SimpleNamespace(content="d"),
        location=SimpleNamespace(display_name="Room"),
        attendees=[SimpleNamespace(
            email_address=SimpleNamespace(address="x@x.com"))])
    prov = MicrosoftProvider()
    prov._client = make_client(events=[ev])
    out = prov.calendar().list_events()[0]
    assert out.id == "e1"
    assert out.summary == "Mtg"
    assert out.location == "Room"
    assert out.attendees == ["x@x.com"]


def test_calendar_delete(provider):
    prov = MicrosoftProvider()
    prov._client = make_client()
    prov.calendar().delete_event("e1")   # no exception = async delete driven


def test_files_list_maps(provider):
    d = SimpleNamespace(
        id="f1", name="doc.pdf", size=99,
        file=SimpleNamespace(mime_type="application/pdf"),
        folder=None, last_modified_date_time=None,
        parent_reference=SimpleNamespace(id="p1"))
    prov = MicrosoftProvider()
    prov._client = make_client(files=[d])
    f = prov.files().list_files()[0]
    assert f.id == "f1"
    assert f.size == 99
    assert f.is_folder is False
    assert f.parent_id == "p1"


def test_files_folder_flag(provider):
    d = SimpleNamespace(
        id="d1", name="dir", size=None, file=None,
        folder=SimpleNamespace(child_count=0),
        last_modified_date_time=None,
        parent_reference=None)
    prov = MicrosoftProvider()
    prov._client = make_client(files=[d])
    assert prov.files().list_files()[0].is_folder is True


def test_contacts_list_maps(provider):
    c = SimpleNamespace(
        id="c1", display_name="Al",
        email_addresses=[SimpleNamespace(address="al@x.com")],
        mobile_phone="123", business_phones=["456"])
    prov = MicrosoftProvider()
    prov._client = make_client(contacts=[c])
    out = prov.contacts().list_contacts()[0]
    assert out.name == "Al"
    assert out.emails == ["al@x.com"]
    assert out.phones == ["123", "456"]
