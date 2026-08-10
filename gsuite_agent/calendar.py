"""Google Calendar via the shared OAuth token (google_auth.service).

Every function takes account=None -> resolves to env GOOGLE_ACCOUNT (=why).
No own credentials — google_auth owns the token/scopes.
"""
from __future__ import annotations

from . import google_auth


def _svc(account: str | None):
    return google_auth.service("calendar", "v3", account)


def list_events(calendar_id: str = "primary", time_min: str | None = None,
                time_max: str | None = None, max_results: int = 50,
                account: str | None = None) -> list:
    params = {"calendarId": calendar_id, "maxResults": max_results,
              "singleEvents": True, "orderBy": "startTime"}
    if time_min:
        params["timeMin"] = time_min
    if time_max:
        params["timeMax"] = time_max
    r = _svc(account).events().list(**params).execute()
    return r.get("items", [])


def create_event(summary: str, start_iso: str, end_iso: str, description: str = "",
                 attendees: list | None = None, calendar_id: str = "primary",
                 account: str | None = None) -> str:
    body = {
        "summary": summary,
        "description": description,
        "start": {"dateTime": start_iso},
        "end": {"dateTime": end_iso},
    }
    if attendees:
        body["attendees"] = [{"email": a} for a in attendees]
    ev = _svc(account).events().insert(calendarId=calendar_id, body=body).execute()
    return ev["id"]


def update_event(event_id: str, calendar_id: str = "primary",
                 account: str | None = None, **fields):
    return _svc(account).events().patch(
        calendarId=calendar_id, eventId=event_id, body=fields).execute()


def delete_event(event_id: str, calendar_id: str = "primary",
                 account: str | None = None):
    _svc(account).events().delete(calendarId=calendar_id, eventId=event_id).execute()


def list_calendars(account: str | None = None) -> list:
    r = _svc(account).calendarList().list().execute()
    return r.get("items", [])
