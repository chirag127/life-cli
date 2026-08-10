import json

import pytest

from gsuite_agent import request


class FakeMail:
    def __init__(self):
        self.sent = []
        self.searched = []
        self.inboxed = 0

    def send(self, to, subject, body, attachments=None):
        self.sent.append({"to": to, "subject": subject, "body": body})

    def search(self, query):
        self.searched.append(query)
        return [{"id": 1}]

    def list_inbox(self):
        self.inboxed += 1
        return [{"id": 9}]


FIELDS = {
    "name": "Chirag",
    "PAN": "ABCDE1234F",
    "folio": "123/45",
    "registered_email": "me@gmail.com",
    "address": "1 Road",
}
AMC_FIELDS = {
    "name": "Chirag",
    "pan": "ABCDE1234F",
    "folio": "123/45",
    "registered_email": "me@gmail.com",
    "address": "1 Road",
    "scheme_name": "Bluechip",
    "amc_name": "HDFC",
}


def test_load_template_rta():
    t = request.load_template("statement-of-account")
    assert t["recipient_type"] == "RTA"
    assert "Statement of Account" in t["subject"]
    assert "{name}" in t["body"]
    assert not t["body"].lower().startswith("subject:")


def test_load_template_amc_literature():
    t = request.load_template("forms")
    assert t["recipient_type"] == "AMC"
    assert "{scheme_name}" in t["subject"]
    assert not t["body"].lower().startswith("subject:")


def test_load_template_unknown_raises():
    with pytest.raises(KeyError):
        request.load_template("nope")


def test_render_fills_placeholders():
    r = request.render("statement-of-account", **FIELDS)
    assert "ABCDE1234F" in r["subject"]
    assert "Chirag" in r["body"]
    assert "{" not in r["body"]


def test_render_amc_literature():
    r = request.render("factsheet", **AMC_FIELDS)
    assert "Bluechip" in r["subject"] and "HDFC" in r["subject"]
    assert "Bluechip" in r["body"]


def test_render_missing_field_raises():
    with pytest.raises(KeyError):
        request.render("statement-of-account", name="x")


def test_send_request_calls_mail():
    m = FakeMail()
    res = request.send_request(m, "statement-of-account", "rta@cams.com", **FIELDS)
    assert m.sent == [{"to": "rta@cams.com", "subject": res["subject"], "body": res["body"]}]
    assert res["to"] == "rta@cams.com"


def test_placeholders_dedup():
    assert request._placeholders("{a} {a}", "{b}") == {"a", "b"}


def test_split_subject_present():
    assert request._split_subject("Subject: Hi\n\nBody") == ("Hi", "Body")


def test_split_subject_absent():
    assert request._split_subject("Body only") == ("", "Body only")


def test_registry_merges_both_indexes():
    reg = request._registry()
    assert "statement-of-account" in reg
    assert "forms" in reg


def test_cli_list_templates(capsys, monkeypatch):
    monkeypatch.setattr(request.sys, "argv", ["mail-agent", "list-templates"])
    assert request.main() == 0
    out = json.loads(capsys.readouterr().out)
    assert "statement-of-account" in out


def test_cli_send_request(capsys, monkeypatch):
    m = FakeMail()
    monkeypatch.setattr(request, "mail", m)
    argv = [
        "send-request", "--key", "statement-of-account", "--to", "rta@cams.com",
        "--field", "name=Chirag", "--field", "PAN=ABCDE1234F", "--field", "folio=1",
        "--field", "registered_email=me@x.com", "--field", "address=Road",
    ]
    assert request.main(argv) == 0
    assert m.sent and m.sent[0]["to"] == "rta@cams.com"


def test_cli_search(capsys, monkeypatch):
    m = FakeMail()
    monkeypatch.setattr(request, "mail", m)
    assert request.main(["search", "from cams"]) == 0
    assert m.searched == ["from cams"]


def test_cli_inbox(capsys, monkeypatch):
    m = FakeMail()
    monkeypatch.setattr(request, "mail", m)
    assert request.main(["inbox"]) == 0
    assert m.inboxed == 1


def test_cli_fetch_cas(capsys, monkeypatch):
    monkeypatch.setattr(request.cas, "find_cas_email_and_download", lambda mod, out: f"{out}/cas.pdf")
    assert request.main(["fetch-cas", "--out", "/o"]) == 0
    assert capsys.readouterr().out.strip() == "/o/cas.pdf"


def test_bad_field_raises():
    with pytest.raises(SystemExit):
        request._parse_fields(["noequals"])
