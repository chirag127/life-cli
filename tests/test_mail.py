import pytest

from gsuite_agent import mail


class FakeProc:
    def __init__(self, stdout="", returncode=0, stderr=""):
        self.stdout = stdout
        self.returncode = returncode
        self.stderr = stderr


@pytest.fixture
def run(monkeypatch):
    calls = []

    def fake_run(cmd, capture_output, text, encoding):
        calls.append(cmd)
        return fake_run.proc

    fake_run.proc = FakeProc(stdout="[]")
    monkeypatch.setattr(mail.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(mail.subprocess, "run", fake_run)
    return calls, fake_run


def _args(cmd):
    return cmd[cmd.index("-c") + 2:]


def test_prepends_json_and_config(run):
    calls, fr = run
    mail.list_mailboxes()
    cmd = calls[0]
    assert cmd[0] == "/usr/bin/himalaya"
    assert cmd[1] == "--json"
    assert cmd[2] == "-c"
    assert cmd[3] == mail.HIMALAYA_CONFIG_PATH


def test_bin_missing_raises(monkeypatch):
    monkeypatch.setattr(mail.shutil, "which", lambda name: None)
    with pytest.raises(RuntimeError, match="binary not found"):
        mail.list_mailboxes()


def test_nonzero_returncode_raises(run):
    calls, fr = run
    fr.proc = FakeProc(returncode=1, stderr="boom")
    with pytest.raises(RuntimeError, match="failed \\(1\\): boom"):
        mail.search("x")


def test_empty_stdout_yields_list(run):
    calls, fr = run
    fr.proc = FakeProc(stdout="   ")
    assert mail.search("q") == []


def test_list_inbox_args_and_parse(run):
    calls, fr = run
    fr.proc = FakeProc(stdout='[{"id": 1}]')
    assert mail.list_inbox("sent", page=2, page_size=10) == [{"id": 1}]
    assert _args(calls[0]) == ["envelope", "list", "-m", "sent", "--page", "2", "--page-size", "10"]


def test_list_inbox_defaults(run):
    calls, fr = run
    mail.list_inbox()
    assert _args(calls[0]) == ["envelope", "list", "-m", "inbox", "--page", "1", "--page-size", "50"]


def test_search_args_and_parse(run):
    calls, fr = run
    fr.proc = FakeProc(stdout='[{"id": 3}, {"id": 4}]')
    assert mail.search("from cams") == [{"id": 3}, {"id": 4}]
    assert _args(calls[0]) == ["envelope", "search", "from cams"]


def test_read_args_and_parse(run):
    calls, fr = run
    fr.proc = FakeProc(stdout='{"subject": "Hi", "body": "x"}')
    assert mail.read(42) == {"subject": "Hi", "body": "x"}
    assert _args(calls[0]) == ["message", "read", "42"]


def test_send_args_no_attachments(run):
    calls, fr = run
    mail.send("to@x.com", "Subj", "Body")
    assert _args(calls[0]) == [
        "message", "compose", "--to", "to@x.com",
        "--subject", "Subj", "--body", "Body", "--send",
    ]


def test_send_args_with_attachments(run):
    calls, fr = run
    mail.send("to@x.com", "S", "B", attachments=["/a.pdf", "/b.pdf"])
    assert _args(calls[0]) == [
        "message", "compose", "--to", "to@x.com", "--subject", "S", "--body", "B",
        "--attachment", "/a.pdf", "--attachment", "/b.pdf", "--send",
    ]


def test_send_returns_none(run):
    calls, fr = run
    assert mail.send("a@b.com", "s", "b") is None


def test_download_attachments_args_and_new_files(run, tmp_path, monkeypatch):
    calls, fr = run
    out = tmp_path / "dl"
    new_pdf = out / "cas.pdf"

    def fake_run(cmd, capture_output, text, encoding):
        calls.append(cmd)
        new_pdf.write_text("pdf")
        return FakeProc(stdout="")

    monkeypatch.setattr(mail.subprocess, "run", fake_run)
    result = mail.download_attachments(7, str(out))
    assert result == [str(new_pdf)]
    assert _args(calls[0]) == ["attachment", "download", "7", "--downloads-dir", str(out)]


def test_download_ignores_preexisting(run, tmp_path, monkeypatch):
    calls, fr = run
    out = tmp_path / "dl"
    out.mkdir()
    (out / "old.txt").write_text("old")
    new_pdf = out / "new.pdf"

    def fake_run(cmd, capture_output, text, encoding):
        new_pdf.write_text("pdf")
        return FakeProc(stdout="")

    monkeypatch.setattr(mail.subprocess, "run", fake_run)
    assert mail.download_attachments(1, str(out)) == [str(new_pdf)]


def test_list_mailboxes_args_and_parse(run):
    calls, fr = run
    fr.proc = FakeProc(stdout='["INBOX", "Sent"]')
    assert mail.list_mailboxes() == ["INBOX", "Sent"]
    assert _args(calls[0]) == ["mailbox", "list"]


def test_run_uses_capture_and_text(run, monkeypatch):
    seen = {}

    def fake_run(cmd, capture_output, text, encoding):
        seen.update(capture_output=capture_output, text=text, encoding=encoding)
        return FakeProc(stdout="[]")

    monkeypatch.setattr(mail.subprocess, "run", fake_run)
    mail.list_mailboxes()
    assert seen == {"capture_output": True, "text": True, "encoding": "utf-8"}
