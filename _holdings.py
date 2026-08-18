import casparser, json, re
PDF = r"C:/g/ws/repos/own/life-cli-secrets/cas/MAR2025_AA49435936_TXN.pdf"
obj = json.loads(casparser.read_cas_pdf(PDF, "OQVPS7357P", output="json"))

mfs = []
for a in obj.get("accounts", []):
    mfs += a.get("mutual_funds", [])

# derive AMC from scheme name (text before first ' - ' after the 'CODE -' prefix)
def amc_of(name):
    # names look like "CODE - AMC Name Fund ... - Direct Growth"
    parts = name.split(" - ")
    return parts[1].strip() if len(parts) > 1 else name

amcs = {}
total_val = 0.0
for m in mfs:
    nm = m["name"]
    amc = amc_of(nm)
    # collapse to fund-house root (first 2-3 words)
    root = re.match(r"([A-Za-z0-9&]+(?:\s+[A-Za-z0-9&]+){0,3})", amc).group(1)
    v = float(m.get("value", 0) or 0)
    total_val += v
    amcs.setdefault(root, {"schemes": [], "value": 0.0})
    amcs[root]["schemes"].append((nm, v))
    amcs[root]["value"] += v

print(f"=== {len(mfs)} MF holdings, total Rs {total_val:,.2f}, across {len(amcs)} fund houses ===\n")
for amc in sorted(amcs, key=lambda a: -amcs[a]["value"]):
    print(f"{amc:45} Rs {amcs[amc]['value']:>12,.2f}  ({len(amcs[amc]['schemes'])} schemes)")

# save the canonical holdings for the mailmerge
out = {amc: {"value": round(d["value"],2), "schemes":[s[0] for s in d["schemes"]]} for amc,d in amcs.items()}
json.dump(out, open(r"C:/g/ws/repos/own/life-cli-secrets/holdings.json","w"), indent=2)
print("\nsaved holdings.json")
