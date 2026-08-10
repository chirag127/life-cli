"""Google Contacts (People API) via the shared OAuth token (google_auth.service).

account=None -> resolves to env GOOGLE_ACCOUNT. No own credentials.
"""
from __future__ import annotations

from . import google_auth

_FIELDS = "names,emailAddresses,phoneNumbers"


def _svc(account: str | None):
    return google_auth.service("people", "v1", account)


def list_contacts(page_size: int = 100, account: str | None = None) -> list:
    r = _svc(account).people().connections().list(
        resourceName="people/me", pageSize=page_size, personFields=_FIELDS,
    ).execute()
    return r.get("connections", [])
