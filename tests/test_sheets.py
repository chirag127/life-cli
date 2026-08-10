import pytest

from gsuite_agent import sheets


class FakeReq:
    def __init__(self, log, name, kwargs, result):
        self.log = log
        self.name = name
        self.kwargs = kwargs
        self.result = result

    def execute(self):
        self.log.append((self.name, self.kwargs))
        return self.result


class FakeValues:
    def __init__(self, log, result):
        self.log = log
        self.result = result

    def _mk(self, name):
        def f(**kw):
            return FakeReq(self.log, name, kw, self.result)
        return f

    get = property(lambda s: s._mk("values.get"))
    update = property(lambda s: s._mk("values.update"))
    append = property(lambda s: s._mk("values.append"))
    clear = property(lambda s: s._mk("values.clear"))


class FakeSpreadsheets:
    def __init__(self, log, result):
        self.log = log
        self.result = result

    def create(self, **kw):
        return FakeReq(self.log, "create", kw, self.result)

    def batchUpdate(self, **kw):
        return FakeReq(self.log, "batchUpdate", kw, self.result)

    def values(self):
        return FakeValues(self.log, self.result)


class FakeService:
    def __init__(self, log, result):
        self.log = log
        self.result = result

    def spreadsheets(self):
        return FakeSpreadsheets(self.log, self.result)


@pytest.fixture
def svc(monkeypatch):
    state = {"log": [], "result": {}, "svc_calls": []}

    def fake_service(api, version, account=None):
        state["svc_calls"].append((api, version, account))
        return FakeService(state["log"], state["result"])

    monkeypatch.setattr(sheets.google_auth, "service", fake_service)
    return state


def test_service_wiring(svc):
    sheets.read_range("sid", "A1", account="why")
    assert svc["svc_calls"] == [("sheets", "v4", "why")]


def test_account_defaults_none(svc):
    sheets.read_range("sid", "A1")
    assert svc["svc_calls"][0] == ("sheets", "v4", None)


def test_create(svc):
    svc["result"] = {"spreadsheetId": "abc123"}
    assert sheets.create("My Sheet", account="chirag") == "abc123"
    name, kw = svc["log"][0]
    assert name == "create"
    assert kw["body"] == {"properties": {"title": "My Sheet"}}
    assert kw["fields"] == "spreadsheetId"


def test_read_range_returns_values(svc):
    svc["result"] = {"values": [["a", "b"], ["c"]]}
    assert sheets.read_range("sid", "Sheet1!A1:B2") == [["a", "b"], ["c"]]
    name, kw = svc["log"][0]
    assert name == "values.get"
    assert kw == {"spreadsheetId": "sid", "range": "Sheet1!A1:B2"}


def test_read_range_empty(svc):
    svc["result"] = {}
    assert sheets.read_range("sid", "A1") == []


def test_write_range(svc):
    sheets.write_range("sid", "A1", [[1, 2]])
    name, kw = svc["log"][0]
    assert name == "values.update"
    assert kw == {
        "spreadsheetId": "sid", "range": "A1",
        "valueInputOption": "USER_ENTERED", "body": {"values": [[1, 2]]},
    }


def test_append_rows(svc):
    sheets.append_rows("sid", "A1", [[9]])
    name, kw = svc["log"][0]
    assert name == "values.append"
    assert kw == {
        "spreadsheetId": "sid", "range": "A1",
        "valueInputOption": "USER_ENTERED", "insertDataOption": "INSERT_ROWS",
        "body": {"values": [[9]]},
    }


def test_add_sheet(svc):
    sheets.add_sheet("sid", "Tab2")
    name, kw = svc["log"][0]
    assert name == "batchUpdate"
    assert kw == {
        "spreadsheetId": "sid",
        "body": {"requests": [{"addSheet": {"properties": {"title": "Tab2"}}}]},
    }


def test_clear_range(svc):
    sheets.clear_range("sid", "A1:Z")
    name, kw = svc["log"][0]
    assert name == "values.clear"
    assert kw == {"spreadsheetId": "sid", "range": "A1:Z", "body": {}}
