import pytest

from life_cli import contacts


class FakeExec:
    def __init__(self, result):
        self._result = result

    def execute(self):
        return self._result


class FakeConnections:
    def __init__(self, svc):
        self._svc = svc

    def list(self, resourceName, pageSize, personFields):
        self._svc.calls.append((resourceName, pageSize, personFields))
        return FakeExec(self._svc.result)


class FakePeople:
    def __init__(self, svc):
        self._svc = svc

    def connections(self):
        return FakeConnections(self._svc)


class FakeService:
    def __init__(self):
        self.calls = []
        self.result = {"connections": []}

    def people(self):
        return FakePeople(self)


@pytest.fixture
def svc(monkeypatch):
    s = FakeService()
    seen = []
    monkeypatch.setattr(contacts.google_auth, "service",
                        lambda api, version, account=None: seen.append((api, version, account)) or s)
    s.seen = seen
    return s


def test_service_threads_people_v1_and_account(svc):
    contacts.list_contacts(account="why")
    assert svc.seen == [("people", "v1", "why")]
    assert svc.calls[0] == ("people/me", 100, "names,emailAddresses,phoneNumbers")


def test_default_account_none_and_returns_connections(svc):
    svc.result = {"connections": [{"resourceName": "people/c1"}]}
    out = contacts.list_contacts(page_size=25)
    assert svc.seen[0] == ("people", "v1", None)
    assert svc.calls[0][1] == 25
    assert out == [{"resourceName": "people/c1"}]
