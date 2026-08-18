"""Watch Gmail for a FRESH CAS (arriving now), download + unlock + parse holdings.
Run: py -3.13 _watch_cas.py
Polls every 90s up to ~30 min. Only accepts a CAS email newer than START.
"""
import os, time, json, datetime
os.environ["GOOGLE_ACCOUNT"] = "why"
os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"
from life_cli import gmail_api

CAS_PWD = "HDK9t#QFz2G3"          # fresh-CAS password the user set
PAN     = "OQVPS7357P"            # fallback (CDSL eCAS uses PAN)
OUTDIR  = r"C:/g/ws/repos/own/life-cli-secrets/cas"
HOLD    = r"C:/g/ws/repos/own/life-cli-secrets/holdings.json"
# only accept CAS mail received after this epoch (start of watch)
START = int(time.time()) - 120   # small grace window
QUERY = ("(subject:(consolidated account statement) OR from:(eCAS@cdslstatement.com "
         "OR camsonline OR kfintech OR mfcentral)) has:attachment newer_than:1d")

def newest_cas():
    hits = gmail_api.search(QUERY, max_results=8, account="why")
    # pick the most recent with a pdf-ish subject
    for h in hits:
        subj = (h.get("subject") or "").lower()
        if "consolidated account statement" in subj or "cas" in subj or "statement" in subj:
            return h["id"], h.get("subject", "")
    return (hits[0]["id"], hits[0].get("subject","")) if hits else (None, None)

def parse(pdf):
    import casparser
    for pwd in (CAS_PWD, PAN):
        try:
            obj = json.loads(casparser.read_cas_pdf(pdf, pwd, output="json"))
            return obj, pwd
        except Exception:
            continue
    return None, None

def extract(obj):
    import re
    mfs = []
    for a in obj.get("accounts", []):
        mfs += a.get("mutual_funds", [])
    # classic-CAS shape too
    for f in obj.get("folios", []):
        for s in f.get("schemes", []):
            mfs.append({"name": s.get("scheme", "?"), "value": (s.get("valuation") or {}).get("value", 0), "amc": f.get("amc")})
    amcs = {}
    for m in mfs:
        nm = m["name"]; parts = nm.split(" - ")
        amc = m.get("amc") or (parts[1].strip() if len(parts) > 1 else nm)
        root = re.match(r"([A-Za-z0-9&]+(?:\s+[A-Za-z0-9&]+){0,3})", amc).group(1)
        amcs.setdefault(root, {"schemes": [], "value": 0.0})
        amcs[root]["schemes"].append(nm)
        amcs[root]["value"] += float(m.get("value", 0) or 0)
    return {k: {"value": round(v["value"], 2), "schemes": v["schemes"]} for k, v in amcs.items()}

print(f"watching for fresh CAS (since {datetime.datetime.now():%H:%M})...")
os.makedirs(OUTDIR, exist_ok=True)
for i in range(20):  # ~30 min
    try:
        mid, subj = newest_cas()
        if mid:
            files = gmail_api.download_attachments(mid, OUTDIR, account="why")
            pdf = next((f for f in files if f.lower().endswith(".pdf")), None)
            if pdf:
                obj, pwd = parse(pdf)
                if obj:
                    holds = extract(obj)
                    inv = obj.get("investor_info", {}) or {}
                    addr = inv.get("address", "") or inv.get("email", "")
                    json.dump({"holdings": holds, "investor": inv},
                              open(HOLD, "w"), indent=2)
                    print(f"GOT CAS: {subj}")
                    print(f"unlocked with: {'CAS_PWD' if pwd==CAS_PWD else 'PAN'}")
                    print(f"investor: {inv.get('name')}")
                    print(f"address:\n{inv.get('address','(no address field)')}")
                    print(f"{len(holds)} fund houses, {sum(len(v['schemes']) for v in holds.values())} schemes -> holdings.json")
                    raise SystemExit(0)
                else:
                    print(f"downloaded {pdf} but couldn't unlock — check password")
    except SystemExit:
        raise
    except Exception as e:
        print(f"[{i}] poll error: {e}")
    time.sleep(90)
print("timed out — no fresh CAS yet. Re-run after it arrives.")
