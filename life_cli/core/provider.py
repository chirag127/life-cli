"""Provider protocol — every provider adapter (Google, Microsoft, ...) implements this.

The platform depends on these Protocols, never on a concrete provider. A capabilities
dict lets a provider declare what it actually supports (labels vs folders, drive, etc.)
so callers can degrade gracefully instead of forcing a lowest common denominator.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from life_cli.core.models import CalendarEvent, Contact, DriveFile, Message


@runtime_checkable
class MailProvider(Protocol):
    def send(self, to: str, subject: str, body: str,
             attachments: list[str] | None = None) -> str: ...
    def search(self, query: str, max_results: int = 50) -> list[Message]: ...
    def list_inbox(self, page_size: int = 50) -> list[Message]: ...
    def read(self, msg_id: str) -> Message: ...
    def download_attachments(self, msg_id: str, out_dir: str) -> list[str]: ...


@runtime_checkable
class CalendarProvider(Protocol):
    def list_events(self, time_min=None, time_max=None,
                    max_results: int = 50) -> list[CalendarEvent]: ...
    def create_event(self, ev: CalendarEvent) -> str: ...
    def update_event(self, event_id: str, **fields) -> None: ...
    def delete_event(self, event_id: str) -> None: ...


@runtime_checkable
class FileProvider(Protocol):
    def list_files(self, query: str | None = None) -> list[DriveFile]: ...
    def download(self, file_id: str, dest_path: str) -> str: ...
    def upload(self, local_path: str, folder_id: str | None = None) -> str: ...
    def delete(self, file_id: str) -> None: ...


@runtime_checkable
class ContactProvider(Protocol):
    def list_contacts(self) -> list[Contact]: ...


class Provider:
    """Base a concrete provider extends. Declares which sub-providers it offers."""
    name: str = "base"
    capabilities: dict[str, bool] = {}

    def mail(self) -> MailProvider | None: return None
    def calendar(self) -> CalendarProvider | None: return None
    def files(self) -> FileProvider | None: return None
    def contacts(self) -> ContactProvider | None: return None
