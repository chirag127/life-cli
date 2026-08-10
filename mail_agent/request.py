"""Templates -> render -> send. CLI: list-templates, send-request, fetch-cas, inbox, search."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from string import Formatter

from mail_agent import cas, mail

TEMPLATES = Path(__file__).resolve().parent / "templates"
_INDEX = TEMPLATES / "index.json"
_INDEX_AMC = TEMPLATES / "index-amc-literature.json"


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _registry() -> dict:
    reg = dict(_load_json(_INDEX))
    for entry in _load_json(_INDEX_AMC):
        reg[Path(entry["template"]).stem] = {
            "file": entry["template"],
            "recipient_type": entry["recipient_type"],
            "subject": entry["subject"],
        }
    return reg


def _split_subject(text: str) -> tuple[str, str]:
    head, _, rest = text.partition("\n")
    if head.lower().startswith("subject:"):
        return head[len("subject:"):].strip(), rest.lstrip("\n")
    return "", text


def load_template(key: str) -> dict:
    reg = _registry()
    if key not in reg:
        raise KeyError(f"unknown template {key!r}; have {sorted(reg)}")
    meta = reg[key]
    text = (TEMPLATES / meta["file"]).read_text(encoding="utf-8").strip("\n")
    file_subject, body = _split_subject(text)
    return {
        "subject": meta.get("subject") or file_subject,
        "body": body,
        "recipient_type": meta["recipient_type"],
    }


def _placeholders(*texts: str) -> set[str]:
    return {name for t in texts for _, name, _, _ in Formatter().parse(t) if name}


def render(key: str, **fields) -> dict:
    tpl = load_template(key)
    missing = _placeholders(tpl["subject"], tpl["body"]) - set(fields)
    if missing:
        raise KeyError(f"missing fields for {key!r}: {sorted(missing)}")
    return {"subject": tpl["subject"].format(**fields), "body": tpl["body"].format(**fields)}


def send_request(mail_module, key: str, to: str, **fields) -> dict:
    rendered = render(key, **fields)
    mail_module.send(to=to, subject=rendered["subject"], body=rendered["body"])
    return {"to": to, **rendered}


def _parse_fields(pairs: list[str]) -> dict:
    out = {}
    for p in pairs:
        k, sep, v = p.partition("=")
        if not sep:
            raise SystemExit(f"bad --field {p!r}; use name=value")
        out[k.strip()] = v
    return out


def _cmd_list_templates(_):
    print(json.dumps(_registry(), indent=2))


def _cmd_send_request(args):
    res = send_request(mail, args.key, args.to, **_parse_fields(args.field or []))
    print(json.dumps(res, indent=2))


def _cmd_fetch_cas(args):
    print(cas.find_cas_email_and_download(mail, args.out))


def _cmd_inbox(_):
    print(json.dumps(mail.list_inbox(), indent=2))


def _cmd_search(args):
    print(json.dumps(mail.search(args.query), indent=2))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="mail-agent")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list-templates").set_defaults(func=_cmd_list_templates)

    s = sub.add_parser("send-request")
    s.add_argument("--key", required=True)
    s.add_argument("--to", required=True)
    s.add_argument("--field", action="append", metavar="name=value")
    s.set_defaults(func=_cmd_send_request)

    f = sub.add_parser("fetch-cas")
    f.add_argument("--out", required=True)
    f.set_defaults(func=_cmd_fetch_cas)

    sub.add_parser("inbox").set_defaults(func=_cmd_inbox)

    q = sub.add_parser("search")
    q.add_argument("query")
    q.set_defaults(func=_cmd_search)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv if argv is not None else sys.argv[1:])
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
