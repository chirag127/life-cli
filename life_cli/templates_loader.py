"""RTA statement-request templates: load index + render body/subject from placeholders."""

from __future__ import annotations

import json
from importlib.resources import files
from typing import TypedDict

_PKG = "life_cli.templates"
FIELDS = ("name", "PAN", "folio", "registered_email", "address")


class Template(TypedDict):
    file: str
    recipient_type: str
    subject: str


def load_index() -> dict[str, Template]:
    return json.loads(files(_PKG).joinpath("index.json").read_text(encoding="utf-8"))


def _body_text(key: str) -> str:
    entry = load_index()[key]
    return files(_PKG).joinpath(entry["file"]).read_text(encoding="utf-8")


def render(key: str, **fields: str) -> dict[str, str]:
    entry = load_index()[key]
    values = {f: fields.get(f, "") for f in FIELDS}
    return {
        "recipient_type": entry["recipient_type"],
        "subject": entry["subject"].format_map(values),
        "body": _body_text(key).format_map(values),
    }
