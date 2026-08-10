import json

import pytest

from life_cli import gtool


@pytest.fixture
def spy(monkeypatch):
    """Replace every dispatched module fn with a recorder returning a marker."""
    calls = {}

    def rec(mod, name, ret=None):
        def f(*args, **kwargs):
            calls[name] = {"args": args, "kwargs": kwargs}
            return ret if ret is not None else name
        monkeypatch.setattr(mod, name, f)

    rec(gtool.mail, "send", "msgid")
    rec(gtool.mail, "list_inbox", [{"id": "1"}])
    rec(gtool.mail, "search", [{"id": "2"}])
    rec(gtool.drive_mod, "list_files", [])
    rec(gtool.drive_mod, "search", [])
    rec(gtool.drive_mod, "download", "/d/f")
    rec(gtool.drive_mod, "upload", "fid")
    rec(gtool.drive_mod, "delete", None)
    rec(gtool.drive_mod, "share", {"id": "p"})
    rec(gtool.drive_mod, "rclone_sync", "synced")
    rec(gtool.docs, "create", "docid")
    rec(gtool.docs, "read", "text")
    rec(gtool.docs, "append_text", None)
    rec(gtool.docs, "export", "/d/x.pdf")
    rec(gtool.sheets, "create", "sid")
    rec(gtool.sheets, "read_range", [["a"]])
    rec(gtool.sheets, "write_range", {})
    rec(gtool.sheets, "append_rows", {})
    rec(gtool.cal, "list_events", [])
    rec(gtool.cal, "create_event", "evid")
    rec(gtool.cal, "delete_event", None)
    rec(gtool.cas, "find_cas_email_and_download", "/d/cas.pdf")
    rec(gtool.google_auth, "accounts", ["chirag", "why"])
    return calls


def run(capsys, *argv):
    assert gtool.main(list(argv)) == 0
    return json.loads(capsys.readouterr().out)


def test_mail_send(spy, capsys):
    out = run(capsys, "mail", "send", "--to", "a@b.c", "--subject", "hi", "--body", "yo", "--attach", "f.pdf")
    assert out == "msgid"
    assert spy["send"]["args"] == ("a@b.c", "hi", "yo", ["f.pdf"])
    assert spy["send"]["kwargs"] == {"account": None}


def test_global_account_forwarded(spy, capsys):
    run(capsys, "-A", "chirag", "mail", "search", "q")
    assert spy["search"]["kwargs"]["account"] == "chirag"


def test_mail_inbox_max(spy, capsys):
    run(capsys, "mail", "inbox", "--mailbox", "SENT", "-n", "5")
    assert spy["list_inbox"]["args"] == ("SENT",)
    assert spy["list_inbox"]["kwargs"] == {"page_size": 5, "account": None}


def test_drive_ls(spy, capsys):
    run(capsys, "drive", "ls", "-q", "trashed=false", "-n", "3")
    assert spy["list_files"]["args"] == ("trashed=false", 3)


def test_drive_upload(spy, capsys):
    run(capsys, "drive", "upload", "x.txt", "--folder", "F", "--name", "N")
    assert spy["upload"]["args"] == ("x.txt", "F", "N")


def test_drive_share_role(spy, capsys):
    run(capsys, "drive", "share", "fid", "u@x.c", "--role", "writer")
    assert spy["share"]["args"] == ("fid", "u@x.c", "writer")


def test_drive_sync_no_account(spy, capsys):
    run(capsys, "drive", "sync", "src", "dst")
    assert spy["rclone_sync"]["args"] == ("src", "dst")


def test_docs_export_mime(spy, capsys):
    run(capsys, "docs", "export", "d1", "out.pdf", "--mime", "text/plain")
    assert spy["export"]["args"] == ("d1", "out.pdf", "text/plain")


def test_sheets_write_row_split(spy, capsys):
    run(capsys, "sheets", "write", "sid", "A1", "a", "b", "|", "c", "d")
    assert spy["write_range"]["args"] == ("sid", "A1", [["a", "b"], ["c", "d"]])


def test_sheets_append_single_row(spy, capsys):
    run(capsys, "sheets", "append", "sid", "A1", "x", "y")
    assert spy["append_rows"]["args"] == ("sid", "A1", [["x", "y"]])


def test_cal_create_attendees(spy, capsys):
    run(capsys, "cal", "create", "Mtg", "S", "E", "--desc", "d", "--attendee", "a@x", "--attendee", "b@y")
    assert spy["create_event"]["args"] == ("Mtg", "S", "E", "d", ["a@x", "b@y"], "primary")


def test_cal_events_range(spy, capsys):
    run(capsys, "cal", "events", "--from", "T0", "--to", "T1", "-n", "9")
    assert spy["list_events"]["args"] == ("primary", "T0", "T1", 9)


def test_cas_fetch_passes_mail_module(spy, capsys):
    out = run(capsys, "cas", "fetch", "/tmp/out")
    assert out == "/d/cas.pdf"
    assert spy["find_cas_email_and_download"]["args"] == (gtool.mail, "/tmp/out")


def test_accounts_list(spy, capsys):
    assert run(capsys, "accounts", "list") == ["chirag", "why"]


def test_no_group_errors(capsys):
    with pytest.raises(SystemExit):
        gtool.main([])


def test_rows_helper():
    assert gtool._rows(["a", "|", "b", "c"]) == [["a"], ["b", "c"]]
    assert gtool._rows(["x"]) == [["x"]]
