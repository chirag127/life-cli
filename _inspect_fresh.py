import casparser, json
PDF = None
import glob, os
pdfs = glob.glob(r"C:/g/ws/repos/own/life-cli-secrets/cas/*.pdf")
PDF = max(pdfs, key=os.path.getmtime)
print("newest CAS pdf:", os.path.basename(PDF))
obj = json.loads(casparser.read_cas_pdf(PDF, "HDK9t#QFz2G3", output="json"))
print("file_type:", obj.get("file_type"))
print("top keys:", list(obj.keys()))
folios = obj.get("folios", [])
print("folios:", len(folios))
if folios:
    f0 = folios[0]
    print("folio[0] keys:", list(f0.keys()))
    print("folio[0].amc:", f0.get("amc"))
    print("folio[0].schemes[0]:", json.dumps(f0.get("schemes",[{}])[0], default=str)[:300])
# also accounts shape
accts = obj.get("accounts", [])
print("accounts:", len(accts))
