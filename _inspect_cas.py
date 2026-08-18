import casparser, json
PDF = r"C:/g/ws/repos/own/life-cli-secrets/cas/MAR2025_AA49435936_TXN.pdf"
data = casparser.read_cas_pdf(PDF, "OQVPS7357P")
d = data if isinstance(data, dict) else getattr(data, "__dict__", {})
print("top-level type:", type(data).__name__)
print("keys:", list(d.keys()) if d else "none")
# dump a trimmed view
try:
    js = casparser.read_cas_pdf(PDF, "OQVPS7357P", output="json")
    print("JSON output type:", type(js).__name__)
    obj = json.loads(js) if isinstance(js, str) else js
    print("json keys:", list(obj.keys()))
    print("folios count:", len(obj.get("folios", [])))
    if obj.get("folios"):
        f0 = obj["folios"][0]
        print("folio[0] keys:", list(f0.keys()))
        print("folio[0] amc:", f0.get("amc"))
        if f0.get("schemes"):
            print("scheme[0] keys:", list(f0["schemes"][0].keys()))
            print("scheme[0]:", json.dumps(f0["schemes"][0], default=str)[:300])
except Exception as e:
    print("json mode err:", e)
