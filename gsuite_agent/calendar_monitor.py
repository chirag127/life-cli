"""Watch calendar changes across providers — 'check whatever is changing my calendar'.

Snapshots the next 90 days via the provider-neutral CalendarProvider, diffs two
snapshots by event id, and persists snapshots as JSON so a later run can report
what was added/removed/changed since.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from typing import Any

from gsuite_agent.core.models import CalendarEvent
from gsuite_agent.providers.registry import get_provider

_WINDOW_DAYS = 90
_MAX = 2500
_TRACKED = ("summary", "start", "end", "description", "location", "attendees", "calendar_id")


def snapshot(provider: str, account: str | None = None) -> list[CalendarEvent]:
    cal = get_provider(provider, account).calendar()
    if cal is None:
        raise ValueError(f"provider {provider!r} has no calendar")
    now = datetime.now(timezone.utc)
    return cal.list_events(
        time_min=now.isoformat(),
        time_max=(now + timedelta(days=_WINDOW_DAYS)).isoformat(),
        max_results=_MAX,
    )


def diff(old_snapshot: list[CalendarEvent],
         new_snapshot: list[CalendarEvent]) -> dict[str, list]:
    old = {e.id: e for e in old_snapshot}
    new = {e.id: e for e in new_snapshot}
    added = [new[i] for i in new if i not in old]
    removed = [old[i] for i in old if i not in new]
    changed = [
        {"id": i, "fields": f}
        for i in old if i in new
        for f in [_field_deltas(old[i], new[i])] if f
    ]
    return {"added": added, "removed": removed, "changed": changed}


def _field_deltas(old: CalendarEvent, new: CalendarEvent) -> dict[str, dict[str, Any]]:
    return {
        f: {"old": getattr(old, f), "new": getattr(new, f)}
        for f in _TRACKED
        if getattr(old, f) != getattr(new, f)
    }


def save_snapshot(path: str, events: list[CalendarEvent]) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump([asdict(e) for e in events], fh, default=_json_default, indent=2)


def load_snapshot(path: str) -> list[CalendarEvent]:
    with open(path, encoding="utf-8") as fh:
        return [_from_dict(d) for d in json.load(fh)]


def monitor(provider: str, account: str | None, snapshot_path: str) -> dict[str, list]:
    try:
        prev = load_snapshot(snapshot_path)
    except FileNotFoundError:
        prev = []
    current = snapshot(provider, account)
    save_snapshot(snapshot_path, current)
    return diff(prev, current)


def _json_default(o: Any) -> str:
    if isinstance(o, datetime):
        return o.isoformat()
    raise TypeError(f"not serializable: {type(o)}")


def _from_dict(d: dict[str, Any]) -> CalendarEvent:
    return CalendarEvent(
        id=d["id"], summary=d.get("summary", ""),
        start=_parse_dt(d.get("start")), end=_parse_dt(d.get("end")),
        description=d.get("description", ""), location=d.get("location", ""),
        attendees=d.get("attendees", []), calendar_id=d.get("calendar_id", "primary"),
        extra=d.get("extra", {}))


def _parse_dt(s: str | None) -> datetime:
    if not s:
        return datetime.min
    return datetime.fromisoformat(s)
