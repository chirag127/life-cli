import tomllib
from pathlib import Path

import pytest

from gsuite_agent.config import Config, ConfigError, render_himalaya_config

REQUIRED = {
    "GMAIL_USER": "me@gmail.com",
    "GMAIL_APP_PASSWORD": "abcd efgh ijkl mnop",
    "INVESTOR_PAN": "ABCDE1234F",
    "REGISTERED_EMAIL": "me@gmail.com",
}


@pytest.fixture
def env(monkeypatch):
    for k in ("HIMALAYA_CONFIG_PATH",):
        monkeypatch.delenv(k, raising=False)
    for k, v in REQUIRED.items():
        monkeypatch.setenv(k, v)


def test_load_ok(env):
    cfg = Config.load()
    assert cfg.gmail_user == "me@gmail.com"
    assert cfg.investor_pan == "ABCDE1234F"


@pytest.mark.parametrize("miss", list(REQUIRED))
def test_missing_raises(env, monkeypatch, miss):
    monkeypatch.delenv(miss)
    with pytest.raises(ConfigError):
        Config.load()


def test_override_path(env, monkeypatch, tmp_path):
    p = tmp_path / "x.toml"
    monkeypatch.setenv("HIMALAYA_CONFIG_PATH", str(p))
    assert Config.load().himalaya_config_path == p


def test_render_valid_toml(env, tmp_path):
    dest = render_himalaya_config(Config.load(), tmp_path / "config.toml")
    data = tomllib.loads(Path(dest).read_text(encoding="utf-8"))
    acc = data["accounts"]["gmail"]
    assert acc["email"] == "me@gmail.com"
    assert acc["imap"]["server"] == "imaps://imap.gmail.com:993"
    assert acc["imap"]["sasl"]["plain"]["password"]["raw"] == REQUIRED["GMAIL_APP_PASSWORD"]
    assert acc["smtp"]["server"] == "smtp://smtp.gmail.com:587"
    assert acc["smtp"]["starttls"] is True
    assert acc["mailbox"]["alias"]["sent"] == "[Gmail]/Sent Mail"


def test_render_escapes_quotes(env, monkeypatch, tmp_path):
    monkeypatch.setenv("GMAIL_APP_PASSWORD", 'a"b\\c')
    dest = render_himalaya_config(Config.load(), tmp_path / "c.toml")
    data = tomllib.loads(Path(dest).read_text(encoding="utf-8"))
    assert data["accounts"]["gmail"]["smtp"]["sasl"]["plain"]["password"]["raw"] == 'a"b\\c'
