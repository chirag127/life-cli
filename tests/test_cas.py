import importlib
import sys
import types
from datetime import date

import pytest

from life_cli import cas


def _txns(rate_flows):
    schemes = [{"transactions": [{"date": d, "type": t, "amount": a} for d, t, a in rate_flows], "valuation": {}}]
    return {"folios": [{"schemes": schemes}]}


def test_cas_password_uppercases(monkeypatch):
    monkeypatch.setattr(cas.Config, "load", classmethod(lambda cls: types.SimpleNamespace(investor_pan="abcde1234f")))
    assert cas.cas_password() == "ABCDE1234F"


def test_parse_cas_uses_pan_and_dict_output(monkeypatch):
    calls = {}

    def fake_read(path, pw, output):
        calls.update(path=path, pw=pw, output=output)
        return {"folios": []}

    monkeypatch.setattr(cas.casparser, "read_cas_pdf", fake_read)
    monkeypatch.setattr(cas, "cas_password", lambda cfg=None: "ABCDE1234F")
    out = cas.parse_cas("x.pdf")
    assert out == {"folios": []}
    assert calls == {"path": "x.pdf", "pw": "ABCDE1234F", "output": "dict"}


def test_parse_cas_explicit_password(monkeypatch):
    monkeypatch.setattr(cas.casparser, "read_cas_pdf", lambda p, pw, output: {"pw": pw})
    assert cas.parse_cas("x.pdf", "ZZTOP9999Z") == {"pw": "ZZTOP9999Z"}


def test_compute_xirr_known_value():
    txns = _txns([(date(2020, 1, 1), "PURCHASE", 1000), (date(2021, 1, 1), "REDEMPTION", 1100)])
    r = cas.compute_xirr(txns)
    assert r == pytest.approx(0.10, abs=1e-3)


def test_compute_xirr_uses_valuation_as_final_inflow():
    schemes = [
        {
            "transactions": [{"date": date(2020, 1, 1), "type": "PURCHASE", "amount": 1000}],
            "valuation": {"date": date(2021, 1, 1), "value": 1100},
        }
    ]
    r = cas.compute_xirr({"folios": [{"schemes": schemes}]})
    assert r == pytest.approx(0.10, abs=1e-3)


def test_compute_xirr_skips_noncash():
    txns = _txns(
        [
            (date(2020, 1, 1), "PURCHASE", 1000),
            (date(2020, 6, 1), "STT_TAX", 5),
            (date(2020, 6, 1), "DIVIDEND_REINVEST", 50),
            (date(2021, 1, 1), "REDEMPTION", 1100),
        ]
    )
    assert cas.compute_xirr(txns) == pytest.approx(0.10, abs=1e-3)


def test_compute_xirr_needs_both_signs():
    with pytest.raises(ValueError):
        cas.compute_xirr(_txns([(date(2020, 1, 1), "PURCHASE", 1000)]))


def test_xirr_newton_fallback_matches(monkeypatch):
    monkeypatch.setitem(sys.modules, "pyxirr", None)
    dates = [date(2020, 1, 1), date(2021, 1, 1)]
    amounts = [-1000.0, 1100.0]
    assert cas._xirr(dates, amounts) == pytest.approx(0.10, abs=1e-3)


def test_as_date_formats():
    assert cas._as_date("2020-01-02") == date(2020, 1, 2)
    assert cas._as_date("02-Jan-2020") == date(2020, 1, 2)
    assert cas._as_date(date(2020, 1, 2)) == date(2020, 1, 2)


class FakeMail:
    def __init__(self, hits=None, inbox=None, downloads=None):
        self._hits = hits or {}
        self._inbox = inbox or []
        self._downloads = downloads or []
        self.download_calls = []

    def search(self, q):
        return self._hits.get(q, [])

    def list_inbox(self, page_size=50):
        return self._inbox

    def download_attachments(self, msg_id, out_dir):
        self.download_calls.append((msg_id, out_dir))
        return self._downloads


def test_find_cas_downloads_pdf():
    mail = FakeMail(hits={'subject "CAS"': [{"id": 7}]}, downloads=["/o/cas.pdf", "/o/x.txt"])
    assert cas.find_cas_email_and_download(mail, "/o") == "/o/cas.pdf"
    assert mail.download_calls == [(7, "/o")]


def test_find_cas_via_inbox_fallback():
    inbox = [
        {"id": 1, "subject": "Hi", "from": {"addr": "a@b.com"}},
        {"id": 2, "subject": "Your Consolidated Account Statement", "from": {"addr": "donotreply@camsonline.com"}},
    ]
    mail = FakeMail(inbox=inbox, downloads=["/o/statement.pdf"])
    assert cas.find_cas_email_and_download(mail, "/o") == "/o/statement.pdf"
    assert mail.download_calls == [(2, "/o")]


def test_find_cas_no_email_raises():
    with pytest.raises(LookupError):
        cas.find_cas_email_and_download(FakeMail(), "/o")


def test_find_cas_no_pdf_raises():
    mail = FakeMail(hits={'subject "CAS"': [{"id": 1}]}, downloads=["/o/note.txt"])
    with pytest.raises(LookupError):
        cas.find_cas_email_and_download(mail, "/o")


def test_request_cas_shape():
    r = cas.request_cas()
    assert set(r["providers"]) == {"CAMS", "KFintech", "MFCentral"}
    for p in r["providers"].values():
        assert p["url"].startswith("https://")
        assert p["steps"]
    assert "PAN" in r["password"].upper()
