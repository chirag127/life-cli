import base64

import pytest

from gsuite_agent import takeout
from gsuite_agent.core.models import Message


def _b64(s: str) -> str:
    return base64.urlsafe_b64encode(s.encode()).decode()


class _Mail:
    def __init__(self, hits, bodies):
        self._hits, self._bodies = hits, bodies
        self.searched = []

    def search(self, query, max_results=50):
        self.searched.append(query)
        return self._hits

    def read(self, msg_id):
        return self._bodies[msg_id]


class _Files:
    def __init__(self):
        self.calls = []

    def download(self, file_id, dest_path):
        self.calls.append((file_id, dest_path))
        return dest_path


class _Provider:
    def __init__(self, mail, files):
        self._m, self._f = mail, files

    def mail(self):
        return self._m

    def files(self):
        return self._f


def test_request_takeout_returns_url_and_not_automatable(capsys):
    r = takeout.request_takeout()
    assert r["url"] == takeout.TAKEOUT_URL
    assert r["automatable"] is False
    assert r["steps"]
    assert "takeout.google.com" in capsys.readouterr().out


def test_extract_links_drive_and_manual():
    text = ("archive at https://drive.google.com/file/d/ABCDEFGHIJ12/view and "
            "https://takeout.google.com/settings/takeout/download?j=xyz done")
    ids, manual = takeout._extract_links(text)
    assert ids == ["ABCDEFGHIJ12"]
    assert manual == ["https://takeout.google.com/settings/takeout/download?j=xyz"]


def test_message_text_prefers_body():
    mail = _Mail([], {"m1": Message(id="m1", thread_id=None, sender="", to=[],
                                    subject="", snippet="", body="hi there")})
    assert takeout._message_text(mail, "m1") == "hi there"


def test_message_text_decodes_payload_fallback():
    payload = {"parts": [{"body": {"data": _b64("link https://drive.google.com/open?id=ZZZZZZZZZZ99")}}]}
    mail = _Mail([], {"m2": Message(id="m2", thread_id=None, sender="", to=[],
                                    subject="", snippet="", extra={"payload": payload})})
    assert "ZZZZZZZZZZ99" in takeout._message_text(mail, "m2")


def test_watch_downloads_drive_and_prints_manual(tmp_path, capsys):
    hit = Message(id="m9", thread_id=None, sender="google", to=[], subject="ready",
                  snippet="", body="grab https://drive.google.com/file/d/FILEID1234X/view "
                                   "or https://takeout.google.com/x/download?j=1")
    files = _Files()
    prov = _Provider(_Mail([hit], {"m9": hit}), files)
    out = takeout.watch_for_export(prov, account="why", out_dir=str(tmp_path))
    assert out["message_id"] == "m9"
    assert files.calls == [("FILEID1234X", str(tmp_path / "takeout-FILEID1234X.zip"))]
    assert out["manual_links"] == ["https://takeout.google.com/x/download?j=1"]
    assert "Manual download" in capsys.readouterr().out


def test_watch_times_out_without_email(tmp_path, monkeypatch):
    monkeypatch.setattr(takeout.time, "monotonic", lambda: 1e12)
    prov = _Provider(_Mail([], {}), _Files())
    out = takeout.watch_for_export(prov, poll_seconds=0, timeout_hours=0,
                                   out_dir=str(tmp_path))
    assert out["timed_out"] is True
    assert out["downloaded"] == []


def test_watch_skips_email_without_links_then_times_out(tmp_path, monkeypatch):
    monkeypatch.setattr(takeout.time, "monotonic", lambda: 1e12)
    hit = Message(id="m0", thread_id=None, sender="", to=[], subject="", snippet="",
                  body="no links here")
    prov = _Provider(_Mail([hit], {"m0": hit}), _Files())
    out = takeout.watch_for_export(prov, poll_seconds=0, timeout_hours=0,
                                   out_dir=str(tmp_path))
    assert out.get("timed_out") is True


def test_data_portability_initiates(monkeypatch):
    captured = {}

    class _Archive:
        def initiate(self, body):
            captured["body"] = body

            class R:
                def execute(self_):
                    return {"archiveJobId": "job-1"}
            return R()

    class _Svc:
        def portabilityArchive(self):
            return _Archive()

    from gsuite_agent import google_auth
    monkeypatch.setattr(google_auth, "service",
                        lambda api, v, account: captured.update(api=api, account=account) or _Svc())
    r = takeout.data_portability_export(["myactivity.search"], account="chirag")
    assert r == {"archiveJobId": "job-1"}
    assert captured["api"] == "dataportability"
    assert captured["account"] == "chirag"
    assert captured["body"] == {"resources": ["myactivity.search"]}
