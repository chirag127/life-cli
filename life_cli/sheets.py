"""Google Sheets (v4) — thin wrapper over the shared OAuth service.

Auth = google_auth.service('sheets','v4', account). One token per account, all
scopes; account resolves from arg or env GOOGLE_ACCOUNT.
"""
from __future__ import annotations

from . import google_auth


def _svc(account: str | None = None):
    return google_auth.service("sheets", "v4", account)


def create(title: str, account: str | None = None) -> str:
    r = _svc(account).spreadsheets().create(
        body={"properties": {"title": title}}, fields="spreadsheetId"
    ).execute()
    return r["spreadsheetId"]


def read_range(sid: str, a1: str, account: str | None = None) -> list[list]:
    r = _svc(account).spreadsheets().values().get(
        spreadsheetId=sid, range=a1
    ).execute()
    return r.get("values", [])


def write_range(sid: str, a1: str, values: list[list], account: str | None = None):
    return _svc(account).spreadsheets().values().update(
        spreadsheetId=sid, range=a1, valueInputOption="USER_ENTERED",
        body={"values": values},
    ).execute()


def append_rows(sid: str, a1: str, rows: list[list], account: str | None = None):
    return _svc(account).spreadsheets().values().append(
        spreadsheetId=sid, range=a1, valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS", body={"values": rows},
    ).execute()


def add_sheet(sid: str, title: str, account: str | None = None):
    return _svc(account).spreadsheets().batchUpdate(
        spreadsheetId=sid,
        body={"requests": [{"addSheet": {"properties": {"title": title}}}]},
    ).execute()


def clear_range(sid: str, a1: str, account: str | None = None):
    return _svc(account).spreadsheets().values().clear(
        spreadsheetId=sid, range=a1, body={},
    ).execute()
