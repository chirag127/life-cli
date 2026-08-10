import pytest

from life_cli import drive


class FakeExec:
    def __init__(self, result):
        self._result = result

    def execute(self):
        return self._result


class FakeFiles:
    def __init__(self, log):
        self.log = log

    def list(self, **kw):
        self.log.append(("list", kw))
        return FakeExec({"files": [{"id": "a"}, {"id": "b"}]})

    def get(self, **kw):
        self.log.append(("get", kw))
        return FakeExec({"id": kw["fileId"], "name": "doc.pdf"})

    def create(self, **kw):
        self.log.append(("create", kw))
        return FakeExec({"id": "NEW"})

    def delete(self, **kw):
        self.log.append(("delete", kw))
        return FakeExec({})

    def get_media(self, **kw):
        self.log.append(("get_media", kw))
        return object()


class FakePerms:
    def __init__(self, log):
        self.log = log

    def create(self, **kw):
        self.log.append(("perm_create", kw))
        return FakeExec({"id": "P"})


class FakeSvc:
    def __init__(self, log):
        self._files = FakeFiles(log)
        self._perms = FakePerms(log)

    def files(self):
        return self._files

    def permissions(self):
        return self._perms


@pytest.fixture
def svc(monkeypatch):
    log = []
    monkeypatch.setattr(drive.google_auth, "service", lambda a, v, account=None: FakeSvc(log))
    monkeypatch.setattr(drive.google_auth, "_account", lambda account=None: account or "why")
    monkeypatch.delenv("RCLONE_REMOTE", raising=False)
    return log


# ---- metadata ----

def test_list_files_passes_query(svc):
    assert drive.list_files(query="q", page_size=5) == [{"id": "a"}, {"id": "b"}]
    _, kw = svc[0]
    assert kw["q"] == "q" and kw["pageSize"] == 5


def test_search_builds_name_contains(svc):
    drive.search("cas")
    assert svc[0][1]["q"] == "name contains 'cas'"


def test_get_metadata(svc):
    assert drive.get_metadata("fid")["name"] == "doc.pdf"
    assert svc[0][1]["fileId"] == "fid"


def test_create_folder_root(svc):
    assert drive.create_folder("F") == "NEW"
    body = svc[0][1]["body"]
    assert body["mimeType"] == drive._FOLDER and "parents" not in body


def test_create_folder_with_parent(svc):
    drive.create_folder("F", parent_id="PID")
    assert svc[0][1]["body"]["parents"] == ["PID"]


def test_delete(svc):
    drive.delete("x")
    assert svc[0] == ("delete", {"fileId": "x"})


def test_share_defaults_reader(svc):
    drive.share("f", "a@b.com")
    body = svc[0][1]["body"]
    assert body == {"type": "user", "role": "reader", "emailAddress": "a@b.com"}


def test_share_custom_role(svc):
    drive.share("f", "a@b.com", role="writer")
    assert svc[0][1]["body"]["role"] == "writer"


# ---- account passthrough ----

def test_account_forwarded_to_service(monkeypatch):
    seen = {}
    monkeypatch.setattr(drive.google_auth, "service",
                        lambda a, v, account=None: seen.update(account=account) or FakeSvc([]))
    drive.list_files(account="chirag")
    assert seen["account"] == "chirag"


# ---- rclone remote resolution ----

def test_remote_account_specific(monkeypatch):
    monkeypatch.setattr(drive.google_auth, "_account", lambda account=None: "why")
    monkeypatch.setenv("RCLONE_REMOTE", "g")
    monkeypatch.setenv("RCLONE_REMOTE_why", "gwhy")
    assert drive._remote(None) == "gwhy"


def test_remote_falls_back_to_generic(monkeypatch):
    monkeypatch.setattr(drive.google_auth, "_account", lambda account=None: "why")
    monkeypatch.delenv("RCLONE_REMOTE_why", raising=False)
    monkeypatch.setenv("RCLONE_REMOTE", "g")
    assert drive._remote(None) == "g"


def test_remote_none(monkeypatch):
    monkeypatch.setattr(drive.google_auth, "_account", lambda account=None: "why")
    monkeypatch.delenv("RCLONE_REMOTE", raising=False)
    monkeypatch.delenv("RCLONE_REMOTE_why", raising=False)
    assert drive._remote(None) is None


# ---- rclone shell-out ----

class FakeProc:
    def __init__(self, stdout="", returncode=0, stderr=""):
        self.stdout, self.returncode, self.stderr = stdout, returncode, stderr


@pytest.fixture
def rclone(monkeypatch):
    calls = []
    monkeypatch.setattr(drive.shutil, "which", lambda n: f"/usr/bin/{n}")

    def fake_run(cmd, capture_output, text, encoding):
        calls.append(cmd)
        return fake_run.proc

    fake_run.proc = FakeProc(stdout="ok")
    monkeypatch.setattr(drive.subprocess, "run", fake_run)
    return calls, fake_run


def test_rclone_bin_missing(monkeypatch):
    monkeypatch.setattr(drive.shutil, "which", lambda n: None)
    with pytest.raises(RuntimeError, match="rclone binary not found"):
        drive._rclone("sync", "a", "b")


def test_rclone_nonzero_raises(rclone):
    calls, fr = rclone
    fr.proc = FakeProc(returncode=3, stderr="boom")
    with pytest.raises(RuntimeError, match="rclone sync failed \\(3\\): boom"):
        drive._rclone("sync", "a", "b")


def test_rclone_sync_args(rclone):
    calls, fr = rclone
    assert drive.rclone_sync("src", "remote:dst") == "ok"
    assert calls[0] == ["/usr/bin/rclone", "sync", "src", "remote:dst", "--progress"]


def test_download_via_rclone(rclone, svc, tmp_path, monkeypatch):
    calls, fr = rclone
    monkeypatch.setenv("RCLONE_REMOTE", "gdrive")
    dest = tmp_path / "out" / "doc.pdf"
    assert drive.download("fid", str(dest)) == str(dest)
    assert calls[0][1] == "copy"
    assert str(dest.parent) in calls[0]


def test_upload_via_rclone_returns_found_id(rclone, svc, monkeypatch):
    calls, fr = rclone
    monkeypatch.setenv("RCLONE_REMOTE", "gdrive")
    monkeypatch.setattr(drive, "search", lambda name, account=None: [{"id": "UP"}])
    assert drive.upload("/local/f.pdf", folder_id="FID") == "UP"
    assert calls[0][1] == "copy" and calls[0][2] == "/local/f.pdf"


def test_upload_via_rclone_no_match_empty(rclone, svc, monkeypatch):
    calls, fr = rclone
    monkeypatch.setenv("RCLONE_REMOTE", "gdrive")
    monkeypatch.setattr(drive, "search", lambda name, account=None: [])
    assert drive.upload("/local/f.pdf") == ""


# ---- API fallback (no remote) ----

def test_download_api_fallback(svc, monkeypatch, tmp_path):
    class FakeDL:
        def __init__(self, fh, req):
            self.fh = fh

        def next_chunk(self):
            self.fh.write(b"data")
            return None, True

    monkeypatch.setitem(
        __import__("sys").modules,
        "googleapiclient.http",
        type("m", (), {"MediaIoBaseDownload": FakeDL})(),
    )
    dest = tmp_path / "f.bin"
    assert drive.download("fid", str(dest)) == str(dest)
    assert dest.read_bytes() == b"data"


def test_upload_api_fallback(svc, monkeypatch):
    monkeypatch.setitem(
        __import__("sys").modules,
        "googleapiclient.http",
        type("m", (), {"MediaFileUpload": lambda *a, **k: "MEDIA"})(),
    )
    assert drive.upload("/local/f.pdf", folder_id="FID", name="x.pdf") == "NEW"
    body = svc[0][1]["body"]
    assert body == {"name": "x.pdf", "parents": ["FID"]}
