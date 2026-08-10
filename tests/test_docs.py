from unittest.mock import MagicMock

import pytest

from gsuite_agent import docs


@pytest.fixture
def svc(monkeypatch):
    services = {}

    def fake_service(api, version, account=None):
        entry = services.setdefault(api, {"svc": MagicMock(name=api)})
        entry["account"] = account
        return entry["svc"]

    monkeypatch.setattr(docs.google_auth, "service", fake_service)
    return services


def _create_returns(d, doc_id):
    d.documents.return_value.create.return_value.execute.return_value = {"documentId": doc_id}


def test_create_passes_account_and_title(svc):
    docs.create("Report", account="why")
    d = svc["docs"]["svc"]
    d.documents.return_value.create.assert_called_once_with(body={"title": "Report"})
    assert svc["docs"]["account"] == "why"


def test_create_returns_id_no_body(svc):
    docs.google_auth.service("docs", "v1")
    d = svc["docs"]["svc"]
    _create_returns(d, "ID1")
    assert docs.create("T") == "ID1"
    d.documents.return_value.batchUpdate.assert_not_called()


def test_create_with_body_appends(svc):
    docs.google_auth.service("docs", "v1")
    d = svc["docs"]["svc"]
    _create_returns(d, "ID2")
    assert docs.create("T", "hello") == "ID2"
    req = d.documents.return_value.batchUpdate.call_args.kwargs["body"]["requests"]
    assert req == [{"insertText": {"endOfSegmentLocation": {}, "text": "hello"}}]


def test_read_concatenates_textruns(svc):
    docs.google_auth.service("docs", "v1")
    d = svc["docs"]["svc"]
    d.documents.return_value.get.return_value.execute.return_value = {
        "body": {"content": [
            {"paragraph": {"elements": [
                {"textRun": {"content": "Hello "}},
                {"textRun": {"content": "world\n"}},
            ]}},
            {"paragraph": {"elements": [{"textRun": {"content": "line2\n"}}]}},
            {"sectionBreak": {}},
        ]}
    }
    assert docs.read("D") == "Hello world\nline2\n"
    d.documents.return_value.get.assert_called_once_with(documentId="D")


def test_append_text_request(svc):
    docs.google_auth.service("docs", "v1")
    d = svc["docs"]["svc"]
    docs.append_text("D", "more", account="chirag")
    body = d.documents.return_value.batchUpdate.call_args.kwargs["body"]
    assert body["requests"] == [{"insertText": {"endOfSegmentLocation": {}, "text": "more"}}]
    assert svc["docs"]["account"] == "chirag"


def test_replace_text_request(svc):
    docs.google_auth.service("docs", "v1")
    d = svc["docs"]["svc"]
    docs.replace_text("D", "foo", "bar")
    reqs = d.documents.return_value.batchUpdate.call_args.kwargs["body"]["requests"]
    assert reqs == [{"replaceAllText": {
        "containsText": {"text": "foo", "matchCase": True},
        "replaceText": "bar",
    }}]


def test_export_writes_file_and_uses_drive(svc, tmp_path, monkeypatch):
    docs.google_auth.service("drive", "v3")
    dr = svc["drive"]["svc"]

    chunks = [(None, False), (None, True)]

    class FakeDL:
        def __init__(self, buf, req):
            buf.write(b"PDFDATA")

        def next_chunk(self):
            return chunks.pop(0)

    monkeypatch.setattr(
        "googleapiclient.http.MediaIoBaseDownload", FakeDL
    )
    dest = tmp_path / "out" / "doc.pdf"
    result = docs.export("DID", str(dest))
    assert result == str(dest)
    assert dest.read_bytes() == b"PDFDATA"
    dr.files.return_value.export_media.assert_called_once_with(
        fileId="DID", mimeType="application/pdf"
    )


def test_export_custom_mime(svc, tmp_path, monkeypatch):
    docs.google_auth.service("drive", "v3")
    dr = svc["drive"]["svc"]

    class FakeDL:
        def __init__(self, buf, req):
            buf.write(b"x")

        def next_chunk(self):
            return None, True

    monkeypatch.setattr("googleapiclient.http.MediaIoBaseDownload", FakeDL)
    dest = tmp_path / "d.docx"
    m = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    docs.export("DID", str(dest), mime=m, account="why")
    dr.files.return_value.export_media.assert_called_once_with(fileId="DID", mimeType=m)
    assert svc["drive"]["account"] == "why"
