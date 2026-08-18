import casparser, json
PDF = r"C:/g/ws/repos/own/life-cli-secrets/cas/MAR2025_AA49435936_TXN.pdf"
js = casparser.read_cas_pdf(PDF, "OQVPS7357P", output="json")
obj = json.loads(js) if isinstance(js, str) else js

print("=== investor:", obj.get("investor_info", {}).get("name"))
print("=== period:", obj.get("statement_period"))
accts = obj.get("accounts", [])
print(f"=== {len(accts)} account blocks ===\n")
amc_names = set()
for a in accts:
    print("ACCOUNT keys:", list(a.keys()))
    print(json.dumps(a, default=str)[:1200])
    print("-"*40)
