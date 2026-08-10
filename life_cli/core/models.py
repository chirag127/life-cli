"""Canonical domain models — provider-neutral. Adapters map native objects to these.

The whole platform speaks these types; Gmail/Outlook/Dropbox/etc. adapters convert
their native shapes into and out of them. Optional provider-specific extras go in
`.extra` rather than forcing a lowest-common-denominator.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Message:
    id: str
    thread_id: str | None
    sender: str
    to: list[str]
    subject: str
    snippet: str
    body: str | None = None
    date: datetime | None = None
    folder: str | None = None          # Gmail label / Outlook folder — normalized name
    unread: bool = False
    has_attachments: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class Attachment:
    name: str
    mime_type: str
    size: int
    data: bytes | None = None
    id: str | None = None


@dataclass
class CalendarEvent:
    id: str
    summary: str
    start: datetime
    end: datetime
    description: str = ""
    location: str = ""
    attendees: list[str] = field(default_factory=list)
    calendar_id: str = "primary"
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class DriveFile:
    id: str
    name: str
    mime_type: str
    size: int | None = None
    modified: datetime | None = None
    is_folder: bool = False
    parent_id: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class Contact:
    id: str
    name: str
    emails: list[str] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)
