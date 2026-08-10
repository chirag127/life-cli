"""Unified gtool CLI — argparse dispatch to gsuite_agent modules, JSON to stdout.

Global --account/-A selects the OAuth token (default env GOOGLE_ACCOUNT=why).
Every subcommand forwards account to the module, which forwards to
google_auth.service(...). Dispatch-only: no business logic here.
"""
from __future__ import annotations

import argparse
import json
import sys

from . import cas, docs, google_auth, sheets
from . import calendar as cal
from . import drive as drive_mod
from . import gmail_api as mail


def _emit(obj) -> None:
    json.dump(obj, sys.stdout, default=str, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


def _build() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="gtool", description="Unified Google Workspace CLI")
    p.add_argument("-A", "--account", default=None, help="account name (default env GOOGLE_ACCOUNT=why)")
    sub = p.add_subparsers(dest="group", required=True)

    def acct(a):
        return a.account or None

    # mail
    m = sub.add_parser("mail").add_subparsers(dest="cmd", required=True)
    s = m.add_parser("send")
    s.add_argument("--to", required=True)
    s.add_argument("--subject", required=True)
    s.add_argument("--body", required=True)
    s.add_argument("--attach", action="append", default=[])
    s.set_defaults(fn=lambda a: mail.send(a.to, a.subject, a.body, a.attach or None, account=acct(a)))
    i = m.add_parser("inbox")
    i.add_argument("--mailbox", default="INBOX")
    i.add_argument("-n", "--max", type=int, default=50)
    i.set_defaults(fn=lambda a: mail.list_inbox(a.mailbox, page_size=a.max, account=acct(a)))
    q = m.add_parser("search")
    q.add_argument("query")
    q.add_argument("-n", "--max", type=int, default=50)
    q.set_defaults(fn=lambda a: mail.search(a.query, a.max, account=acct(a)))

    # drive
    d = sub.add_parser("drive").add_subparsers(dest="cmd", required=True)
    dl = d.add_parser("ls")
    dl.add_argument("-q", "--query", default=None)
    dl.add_argument("-n", "--max", type=int, default=100)
    dl.set_defaults(fn=lambda a: drive_mod.list_files(a.query, a.max, account=acct(a)))
    ds = d.add_parser("search")
    ds.add_argument("name")
    ds.set_defaults(fn=lambda a: drive_mod.search(a.name, account=acct(a)))
    dd = d.add_parser("download")
    dd.add_argument("file_id")
    dd.add_argument("dest")
    dd.set_defaults(fn=lambda a: drive_mod.download(a.file_id, a.dest, account=acct(a)))
    du = d.add_parser("upload")
    du.add_argument("path")
    du.add_argument("--folder", default=None)
    du.add_argument("--name", default=None)
    du.set_defaults(fn=lambda a: drive_mod.upload(a.path, a.folder, a.name, account=acct(a)))
    dr = d.add_parser("rm")
    dr.add_argument("file_id")
    dr.set_defaults(fn=lambda a: drive_mod.delete(a.file_id, account=acct(a)))
    dsh = d.add_parser("share")
    dsh.add_argument("file_id")
    dsh.add_argument("email")
    dsh.add_argument("--role", default="reader")
    dsh.set_defaults(fn=lambda a: drive_mod.share(a.file_id, a.email, a.role, account=acct(a)))
    dsy = d.add_parser("sync")
    dsy.add_argument("src")
    dsy.add_argument("dst")
    dsy.set_defaults(fn=lambda a: drive_mod.rclone_sync(a.src, a.dst))

    # docs
    dc = sub.add_parser("docs").add_subparsers(dest="cmd", required=True)
    dcc = dc.add_parser("create")
    dcc.add_argument("title")
    dcc.add_argument("--body", default="")
    dcc.set_defaults(fn=lambda a: docs.create(a.title, a.body, account=acct(a)))
    dcr = dc.add_parser("read")
    dcr.add_argument("doc_id")
    dcr.set_defaults(fn=lambda a: docs.read(a.doc_id, account=acct(a)))
    dca = dc.add_parser("append")
    dca.add_argument("doc_id")
    dca.add_argument("text")
    dca.set_defaults(fn=lambda a: docs.append_text(a.doc_id, a.text, account=acct(a)))
    dce = dc.add_parser("export")
    dce.add_argument("doc_id")
    dce.add_argument("dest")
    dce.add_argument("--mime", default="application/pdf")
    dce.set_defaults(fn=lambda a: docs.export(a.doc_id, a.dest, a.mime, account=acct(a)))

    # sheets
    sh = sub.add_parser("sheets").add_subparsers(dest="cmd", required=True)
    shc = sh.add_parser("create")
    shc.add_argument("title")
    shc.set_defaults(fn=lambda a: sheets.create(a.title, account=acct(a)))
    shr = sh.add_parser("read")
    shr.add_argument("sid")
    shr.add_argument("range")
    shr.set_defaults(fn=lambda a: sheets.read_range(a.sid, a.range, account=acct(a)))
    shw = sh.add_parser("write")
    shw.add_argument("sid")
    shw.add_argument("range")
    shw.add_argument("values", nargs="+", help="row cells; use '|' to split rows")
    shw.set_defaults(fn=lambda a: sheets.write_range(a.sid, a.range, _rows(a.values), account=acct(a)))
    sha = sh.add_parser("append")
    sha.add_argument("sid")
    sha.add_argument("range")
    sha.add_argument("values", nargs="+", help="row cells; use '|' to split rows")
    sha.set_defaults(fn=lambda a: sheets.append_rows(a.sid, a.range, _rows(a.values), account=acct(a)))

    # cal
    c = sub.add_parser("cal").add_subparsers(dest="cmd", required=True)
    ce = c.add_parser("events")
    ce.add_argument("--calendar", default="primary")
    ce.add_argument("--from", dest="time_min", default=None)
    ce.add_argument("--to", dest="time_max", default=None)
    ce.add_argument("-n", "--max", type=int, default=50)
    ce.set_defaults(fn=lambda a: cal.list_events(a.calendar, a.time_min, a.time_max, a.max, account=acct(a)))
    cc = c.add_parser("create")
    cc.add_argument("summary")
    cc.add_argument("start")
    cc.add_argument("end")
    cc.add_argument("--desc", default="")
    cc.add_argument("--attendee", action="append", default=[])
    cc.add_argument("--calendar", default="primary")
    cc.set_defaults(fn=lambda a: cal.create_event(a.summary, a.start, a.end, a.desc, a.attendee or None, a.calendar, account=acct(a)))
    cr = c.add_parser("rm")
    cr.add_argument("event_id")
    cr.add_argument("--calendar", default="primary")
    cr.set_defaults(fn=lambda a: cal.delete_event(a.event_id, a.calendar, account=acct(a)))

    # cas
    ca = sub.add_parser("cas").add_subparsers(dest="cmd", required=True)
    caf = ca.add_parser("fetch")
    caf.add_argument("out_dir")
    caf.set_defaults(fn=lambda a: cas.find_cas_email_and_download(mail, a.out_dir))

    # accounts
    ac = sub.add_parser("accounts").add_subparsers(dest="cmd", required=True)
    acl = ac.add_parser("list")
    acl.set_defaults(fn=lambda a: google_auth.accounts())
    acc = ac.add_parser("clear")
    acc.add_argument("name", nargs="?", default=None)
    acc.set_defaults(fn=lambda a: {"cleared": google_auth.clear_token(a.name)})

    return p


def _rows(cells: list[str]) -> list[list]:
    rows, cur = [], []
    for c in cells:
        if c == "|":
            rows.append(cur)
            cur = []
        else:
            cur.append(c)
    rows.append(cur)
    return rows


def main(argv: list[str] | None = None) -> int:
    args = _build().parse_args(argv)
    _emit(args.fn(args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
