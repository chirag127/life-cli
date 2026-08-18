import casparser, json, re, glob, os
pdfs = glob.glob(r"C:/g/ws/repos/own/life-cli-secrets/cas/*.pdf")
PDF = max(pdfs, key=os.path.getmtime)
obj = json.loads(casparser.read_cas_pdf(PDF, "HDK9t#QFz2G3", output="json"))

# Known fund-house name prefixes (longest-match first) to group schemes correctly.
HOUSES = [
 "Aditya Birla Sun Life","Axis","Bajaj Finserv","Bandhan","Bank of India","Baroda BNP Paribas",
 "Canara Robeco","DSP","Edelweiss","Franklin","Groww","HDFC","Helios","HSBC","ICICI Prudential",
 "Invesco","ITI","JM Financial","Kotak","LIC","Mahindra Manulife","Mirae Asset","Motilal Oswal",
 "Navi","Nippon India","NJ","Old Bridge","Parag Parikh","PGIM","PPFAS","quant","Quantum",
 "Samco","SBI","Shriram","Sundaram","Tata","Taurus","Trust","Union","UTI","WhiteOak","Zerodha",
 "360 ONE","Abakkus","Angel One"
]
def house_of(scheme):
    for h in HOUSES:
        if scheme.lower().startswith(h.lower()):
            return h
    return scheme.split()[0]  # fallback: first word

amcs = {}
total = 0.0
for f in obj.get("folios", []):
    for s in f.get("schemes", []):
        nm = s.get("scheme","?")
        h = house_of(nm)
        val = (s.get("valuation") or {})
        v = float(val.get("value",0) or 0)
        total += v
        amcs.setdefault(h, {"schemes":[], "value":0.0, "folios":set()})
        amcs[h]["schemes"].append(nm)
        amcs[h]["value"] += v
        amcs[h]["folios"].add(f.get("folio"))

inv = obj.get("investor_info", {}) or {}
out = {
  "investor": {"name": inv.get("name"), "address": inv.get("address"), "email": inv.get("email"), "pan":"OQVPS7357P"},
  "total_value": round(total,2),
  "houses": {h: {"value": round(d["value"],2), "n_schemes": len(d["schemes"]),
                 "schemes": sorted(set(d["schemes"]))} for h,d in amcs.items()}
}
json.dump(out, open(r"C:/g/ws/repos/own/life-cli-secrets/holdings.json","w"), indent=2)

print(f"=== {len(amcs)} fund houses, {sum(len(d['schemes']) for d in amcs.values())} schemes, Rs {total:,.2f} ===\n")
for h in sorted(amcs, key=lambda x:-amcs[x]["value"]):
    print(f"{h:28} Rs {amcs[h]['value']:>11,.2f}  ({len(set(amcs[h]['schemes']))} schemes)")
