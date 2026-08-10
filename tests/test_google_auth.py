"""google_auth — scopes, service build(), token naming, accounts(), login_hint,
missing-secret. All google libs mocked via sys.modules; no network."""

import sys
import types

import pytest

from gsuite_agent import google_auth


# ---- SCOPES ----

def test_scopes_cover_all_five():
    required = [
        "https://www.googleapis.com/auth/gmail.modify",
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/documents",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/calendar",
    ]
    for scope in required:
        assert scope in google_auth.SCOPES


def test_account_arg_wins(monkeypatch):
    monkeypatch.setenv("GOOGLE_ACCOUNT", "why")
    assert google_auth._account("chirag") == "chirag"


def test_account_from_env(monkeypatch):
    monkeypatch.setattr(google_auth, "_load_env", lambda: None)
    monkeypatch.setenv("GOOGLE_ACCOUNT", "why")
    assert google_auth._account(None) == "why"


def test_account_default(monkeypatch):
    monkeypatch.setattr(google_auth, "_load_env", lambda: None)
    monkeypatch.delenv("GOOGLE_ACCOUNT", raising=False)
    assert google_auth._account(None) == "default"


# ---- token file naming ----

def test_token_file_naming():
    assert google_auth._token_file("why").name == "token-why.json"
    assert google_auth._token_file("chirag").name == "token-chirag.json"


# ---- accounts() parses GOOGLE_ACCOUNTS ----

def test_accounts_parses_csv(monkeypatch):
    monkeypatch.setattr(google_auth, "_load_env", lambda: None)
    monkeypatch.setenv("GOOGLE_ACCOUNTS", "chirag, why ,")
    assert google_auth.accounts() == ["chirag", "why"]


def test_accounts_empty(monkeypatch):
    monkeypatch.setattr(google_auth, "_load_env", lambda: None)
    monkeypatch.delenv("GOOGLE_ACCOUNTS", raising=False)
    assert google_auth.accounts() == []


# ---- service() builds build(api, version, credentials=creds) ----

def test_service_builds_with_creds(monkeypatch):
    built = {}
    fake_disc = types.ModuleType("googleapiclient.discovery")
    fake_disc.build = lambda api, version, credentials=None: built.update(
        api=api, version=version, creds=credentials) or "SVC"
    monkeypatch.setitem(sys.modules, "googleapiclient", types.ModuleType("googleapiclient"))
    monkeypatch.setitem(sys.modules, "googleapiclient.discovery", fake_disc)
    monkeypatch.setattr(google_auth, "credentials", lambda account=None: f"CREDS-{account}")

    assert google_auth.service("docs", "v1", account="why") == "SVC"
    assert built == {"api": "docs", "version": "v1", "creds": "CREDS-why"}


# ---- credentials(): reuse cached token, login_hint, missing-secret ----

def _install_google_stubs(monkeypatch, state):
    """Stub the three lazily-imported google modules."""
    tr = types.ModuleType("google.auth.transport.requests")
    tr.Request = lambda: "REQ"

    creds_mod = types.ModuleType("google.oauth2.credentials")

    class Credentials:
        @staticmethod
        def from_authorized_user_file(path, scopes):
            state["loaded"] = (path, scopes)
            return state["cached"]

    creds_mod.Credentials = Credentials

    flow_mod = types.ModuleType("google_auth_oauthlib.flow")

    class InstalledAppFlow:
        @staticmethod
        def from_client_secrets_file(path, scopes):
            state["flow_secret"] = (path, scopes)
            return InstalledAppFlow()

        def run_local_server(self, port=0, **kw):
            state["run_kw"] = kw
            return state["new_creds"]

    flow_mod.InstalledAppFlow = InstalledAppFlow

    for name, mod in [
        ("google", types.ModuleType("google")),
        ("google.auth", types.ModuleType("google.auth")),
        ("google.auth.transport", types.ModuleType("google.auth.transport")),
        ("google.auth.transport.requests", tr),
        ("google.oauth2", types.ModuleType("google.oauth2")),
        ("google.oauth2.credentials", creds_mod),
        ("google_auth_oauthlib", types.ModuleType("google_auth_oauthlib")),
        ("google_auth_oauthlib.flow", flow_mod),
    ]:
        monkeypatch.setitem(sys.modules, name, mod)


class FakeCreds:
    def __init__(self, valid=True, expired=False, refresh_token=None):
        self.valid, self.expired, self.refresh_token = valid, expired, refresh_token
        self.refreshed = False

    def refresh(self, req):
        self.refreshed = True
        self.valid = True

    def to_json(self):
        return '{"tok": 1}'


def test_credentials_reuses_valid_cached_token(monkeypatch, tmp_path):
    state = {"cached": FakeCreds(valid=True), "new_creds": None}
    _install_google_stubs(monkeypatch, state)
    tok = tmp_path / "token-why.json"
    tok.write_text("{}")
    monkeypatch.setattr(google_auth, "_token_file", lambda a: tok)
    monkeypatch.setattr(google_auth, "_account", lambda a=None: "why")

    creds = google_auth.credentials("why")
    assert creds is state["cached"]
    assert state["loaded"][1] == google_auth.SCOPES
    assert "run_kw" not in state  # no browser flow


def test_credentials_refreshes_expired(monkeypatch, tmp_path):
    cached = FakeCreds(valid=False, expired=True, refresh_token="rt")
    state = {"cached": cached, "new_creds": None}
    _install_google_stubs(monkeypatch, state)
    tok = tmp_path / "token-why.json"
    tok.write_text("{}")
    monkeypatch.setattr(google_auth, "_token_file", lambda a: tok)
    monkeypatch.setattr(google_auth, "_account", lambda a=None: "why")
    monkeypatch.setattr(google_auth, "_CFG", tmp_path)

    creds = google_auth.credentials("why")
    assert creds.refreshed is True
    assert tok.read_text() == '{"tok": 1}'


def test_credentials_flow_passes_login_hint(monkeypatch, tmp_path):
    new = FakeCreds(valid=True)
    state = {"cached": None, "new_creds": new}
    _install_google_stubs(monkeypatch, state)
    tok = tmp_path / "token-why.json"  # does not exist
    monkeypatch.setattr(google_auth, "_token_file", lambda a: tok)
    monkeypatch.setattr(google_auth, "_account", lambda a=None: "why")
    monkeypatch.setattr(google_auth, "_CFG", tmp_path)
    monkeypatch.setattr(google_auth, "CLIENT_SECRET", tmp_path / "client.json")
    (tmp_path / "client.json").write_text("{}")
    monkeypatch.setenv("GOOGLE_ACCOUNT_why", "whyiswhen@gmail.com")

    google_auth.credentials("why")
    assert state["run_kw"] == {"login_hint": "whyiswhen@gmail.com"}
    assert tok.read_text() == '{"tok": 1}'


def test_credentials_flow_no_login_hint_when_email_unset(monkeypatch, tmp_path):
    state = {"cached": None, "new_creds": FakeCreds(valid=True)}
    _install_google_stubs(monkeypatch, state)
    tok = tmp_path / "token-x.json"
    monkeypatch.setattr(google_auth, "_token_file", lambda a: tok)
    monkeypatch.setattr(google_auth, "_account", lambda a=None: "x")
    monkeypatch.setattr(google_auth, "_CFG", tmp_path)
    monkeypatch.setattr(google_auth, "CLIENT_SECRET", tmp_path / "client.json")
    (tmp_path / "client.json").write_text("{}")
    monkeypatch.delenv("GOOGLE_ACCOUNT_x", raising=False)

    google_auth.credentials("x")
    assert state["run_kw"] == {}


def test_credentials_missing_secret_raises(monkeypatch, tmp_path):
    state = {"cached": None, "new_creds": None}
    _install_google_stubs(monkeypatch, state)
    tok = tmp_path / "token-why.json"
    monkeypatch.setattr(google_auth, "_token_file", lambda a: tok)
    monkeypatch.setattr(google_auth, "_account", lambda a=None: "why")
    monkeypatch.setattr(google_auth, "CLIENT_SECRET", tmp_path / "missing.json")

    with pytest.raises(FileNotFoundError, match="OAuth client secret missing"):
        google_auth.credentials("why")
