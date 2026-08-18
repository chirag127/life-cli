import casparser
PDF = r"C:/g/ws/repos/own/life-cli-secrets/cas/MAR2025_AA49435936_TXN.pdf"
PWD = "OQVPS7357P"
try:
    data = casparser.read_cas_pdf(PDF, PWD)
except Exception as e:
    print("parse error:", e); raise SystemExit(1)

# casparser returns an object/dict; normalize
d = data if isinstance(data, dict) else data.__dict__
folios = d.get("folios") or (data.folios if hasattr(data, "folios") else [])
print("=== YOUR MUTUAL FUND HOLDINGS (from CAS MAR2025) ===")
amcs = {}
for f in folios:
    f = f if isinstance(f, dict) else f.__dict__
    amc = f.get("amc", "?")
    for s in f.get("schemes", []):
        s = s if isinstance(s, dict) else s.__dict__
        val = s.get("valuation", {})
        val = val if isinstance(val, dict) else getattr(val, "__dict__", {})
        amcs.setdefault(amc, []).append((s.get("scheme", "?"), val.get("value", 0), s.get("close", 0)))
for amc, schemes in amcs.items():
    print(f"\n{amc}:")
    for name, value, units in schemes:
        print(f"   {name[:60]:60}  units={units}  value=Rs {value}")
print(f"\n=== {len(amcs)} AMCs, {sum(len(v) for v in amcs.values())} schemes ===")
print("AMCs:", list(amcs.keys()))
