"""Provider registry — name -> Provider, with lazy adapter imports.

Importing this module pulls in neither Google nor Microsoft SDKs; the adapter
(and its SDK) loads only when its provider is requested.
"""
from __future__ import annotations

import os

from gsuite_agent.core.provider import Provider

_PROVIDERS = ("google", "microsoft")
_DEFAULT = "google"


def list_providers() -> list[str]:
    return list(_PROVIDERS)


def get_provider(name: str, account: str | None = None) -> Provider:
    key = name.lower()
    if key == "google":
        from gsuite_agent.providers.google_provider import GoogleProvider
        return GoogleProvider(account)
    if key == "microsoft":
        from gsuite_agent.providers.microsoft_provider import MicrosoftProvider
        return MicrosoftProvider(account)
    raise ValueError(f"unknown provider {name!r}; known: {', '.join(_PROVIDERS)}")


def resolve(provider: str | None = None, account: str | None = None) -> Provider:
    name = provider or os.environ.get("DEFAULT_PROVIDER", _DEFAULT)
    acct = account or os.environ.get("GOOGLE_ACCOUNT")
    return get_provider(name, acct)
