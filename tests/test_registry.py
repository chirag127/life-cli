import pytest

from life_cli.core.provider import Provider
from life_cli.providers import registry


def test_list_providers():
    assert registry.list_providers() == ["google", "microsoft"]


def test_get_google():
    p = registry.get_provider("google", account="why")
    assert isinstance(p, Provider)
    assert p.name == "google"
    assert p.account == "why"


def test_get_case_insensitive():
    assert registry.get_provider("GOOGLE").name == "google"


def test_get_microsoft():
    p = registry.get_provider("microsoft")
    assert p.name == "microsoft"


def test_get_unknown_raises():
    with pytest.raises(ValueError, match="unknown provider"):
        registry.get_provider("dropbox")


def test_resolve_defaults_to_google(monkeypatch):
    monkeypatch.delenv("DEFAULT_PROVIDER", raising=False)
    monkeypatch.delenv("GOOGLE_ACCOUNT", raising=False)
    p = registry.resolve()
    assert p.name == "google"
    assert p.account is None


def test_resolve_reads_env(monkeypatch):
    monkeypatch.setenv("DEFAULT_PROVIDER", "microsoft")
    monkeypatch.setenv("GOOGLE_ACCOUNT", "chirag")
    p = registry.resolve()
    assert p.name == "microsoft"
    assert p.account == "chirag"


def test_resolve_args_override_env(monkeypatch):
    monkeypatch.setenv("DEFAULT_PROVIDER", "microsoft")
    monkeypatch.setenv("GOOGLE_ACCOUNT", "chirag")
    p = registry.resolve(provider="google", account="why")
    assert p.name == "google"
    assert p.account == "why"
