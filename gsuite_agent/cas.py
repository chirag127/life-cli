"""Mutual-fund CAS: parse, XIRR, mail-fetch, request URLs. Password = PAN uppercase."""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import casparser

from gsuite_agent.config import Config

_CASHIN = {"REDEMPTION", "SWITCH_OUT", "SWITCH_OUT_MERGER", "SEGREGATION"}
_NONCASH = {
    "DIVIDEND_REINVEST",
    "STT_TAX",
    "STAMP_DUTY_TAX",
    "TDS_TAX",
    "MISC",
    "SEGREGATION",
}
_SENDER_HINTS = ("cas", "camsonline", "kfintech", "kfintechonline", "karvy", "cams")


def cas_password(cfg: Config | None = None) -> str:
    return (cfg or Config.load()).investor_pan.upper()


def parse_cas(pdf_path: str, password: str | None = None) -> dict:
    pw = password or cas_password()
    return casparser.read_cas_pdf(pdf_path, pw, output="dict")


def _cashflows(transactions: dict) -> tuple[list[date], list[float]]:
    dates: list[date] = []
    amounts: list[float] = []
    for folio in transactions.get("folios", []):
        for scheme in folio.get("schemes", []):
            for txn in scheme.get("transactions", []):
                ttype = (txn.get("type") or "").upper()
                if ttype in _NONCASH:
                    continue
                amt = txn.get("amount")
                if amt in (None, ""):
                    continue
                value = float(Decimal(str(amt)))
                if value == 0:
                    continue
                flow = abs(value) if ttype in _CASHIN else -abs(value)
                dates.append(_as_date(txn["date"]))
                amounts.append(flow)
            val = scheme.get("valuation") or {}
            mv = val.get("value")
            if mv not in (None, "") and float(Decimal(str(mv))) != 0:
                dates.append(_as_date(val["date"]))
                amounts.append(float(Decimal(str(mv))))
    return dates, amounts


def compute_xirr(transactions: dict) -> float:
    dates, amounts = _cashflows(transactions)
    if len(dates) < 2 or not (any(a > 0 for a in amounts) and any(a < 0 for a in amounts)):
        raise ValueError("need >=2 flows with both signs for XIRR")
    return _xirr(dates, amounts)


def find_cas_email_and_download(mail_module: Any, out_dir: str) -> str:
    envelopes = _search_cas(mail_module)
    if not envelopes:
        raise LookupError("no CAS email found (CAMS/KFintech)")
    for env in envelopes:
        msg_id = env.get("id") or env.get("uid") or env.get("internal_id")
        if msg_id is None:
            continue
        pdfs = [p for p in mail_module.download_attachments(msg_id, out_dir) if p.lower().endswith(".pdf")]
        if pdfs:
            return pdfs[0]
    raise LookupError("CAS email found but no PDF attachment")


def _search_cas(mail_module: Any) -> list:
    seen: dict[Any, dict] = {}
    for q in ('subject "CAS"', 'from "camsonline"', 'from "kfintech"', 'subject "Consolidated Account Statement"'):
        try:
            hits = mail_module.search(q)
        except Exception:
            hits = []
        for env in hits or []:
            key = env.get("id") or env.get("uid") or id(env)
            seen.setdefault(key, env)
    if seen:
        return list(seen.values())
    return [env for env in mail_module.list_inbox(page_size=100) if _looks_like_cas(env)]


def _looks_like_cas(env: dict) -> bool:
    subject = (env.get("subject") or "").lower()
    frm = env.get("from") or {}
    sender = " ".join(str(v) for v in frm.values()).lower() if isinstance(frm, dict) else str(frm).lower()
    blob = f"{subject} {sender}"
    return any(h in blob for h in _SENDER_HINTS)


def request_cas() -> dict:
    return {
        "password": "PAN in UPPERCASE (e.g. ABCDE1234F). PDF is emailed to your registered email.",
        "providers": {
            "CAMS": {
                "url": "https://www.camsonline.com/Investors/Statements/Consolidated-Account-Statement",
                "steps": [
                    "Pick 'Statement Type: Detailed', period 'Since Inception'",
                    "Enter registered email + set a password (or use PAN)",
                    "Submit; PDF arrives by email, encrypted with the password you chose / PAN uppercase",
                ],
            },
            "KFintech": {
                "url": "https://mfs.kfintech.com/investor/General/ConsolidatedAccountStatement",
                "steps": [
                    "Choose 'Detailed' CAS, period since inception",
                    "Enter registered email; submit",
                    "Password-protected PDF emailed; password = PAN uppercase",
                ],
            },
            "MFCentral": {
                "url": "https://www.mfcentral.com/investor/casrequest",
                "steps": [
                    "Login/OTP with registered mobile+email",
                    "Request 'Detailed' CAS across CAMS+KFintech",
                    "PDF emailed; password = PAN uppercase",
                ],
            },
        },
    }


def _as_date(v: Any) -> date:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = str(v)
    for fmt in ("%Y-%m-%d", "%d-%b-%Y", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(s[:10] if fmt == "%Y-%m-%d" else s, fmt).date()
        except ValueError:
            continue
    return datetime.fromisoformat(s).date()


def _xirr(dates: list[date], amounts: list[float]) -> float:
    try:
        from pyxirr import xirr

        rate = xirr(dates, amounts)
        if rate is None:
            raise ValueError("pyxirr returned None (no convergence)")
        return float(rate)
    except ImportError:
        return _xirr_newton(dates, amounts)


def _xirr_newton(dates: list[date], amounts: list[float], guess: float = 0.1) -> float:
    t0 = min(dates)
    years = [(d - t0).days / 365.0 for d in dates]
    rate = guess
    for _ in range(200):
        f = sum(a / (1 + rate) ** y for a, y in zip(amounts, years))
        df = sum(-y * a / (1 + rate) ** (y + 1) for a, y in zip(amounts, years))
        if df == 0:
            break
        step = f / df
        rate -= step
        if abs(step) < 1e-9:
            return rate
    raise ValueError("XIRR Newton did not converge")
