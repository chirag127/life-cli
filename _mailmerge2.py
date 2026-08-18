import casparser, json, re, glob, os
pdfs = glob.glob(r"C:/g/ws/repos/own/life-cli-secrets/cas/*.pdf")
PDF = max(pdfs, key=os.path.getmtime)
obj = json.loads(casparser.read_cas_pdf(PDF, "HDK9t#QFz2G3", output="json"))

HOUSES = ["Aditya Birla Sun Life","Axis","Bajaj Finserv","Bandhan","Bank of India","Baroda BNP Paribas",
 "Canara Robeco","DSP","Edelweiss","Franklin","Groww","HDFC","Helios","HSBC","ICICI Prudential",
 "Invesco","ITI","JM Financial","JM","Kotak","LIC","Mahindra Manulife","Mirae Asset","Motilal Oswal",
 "Navi","Nippon India","NJ","Old Bridge","Parag Parikh","PPFAS","PGIM","quant","Quantum","Samco","SBI",
 "Shriram","Sundaram","Tata","Taurus","Trust","Union","UTI","WhiteOak","Zerodha","360 ONE","Abakkus",
 "Angel One","Capitalmind","AlphaGrep","JioBlackRock"]
def house_of(s):
    for h in HOUSES:
        if s.lower().startswith(h.lower()): return h
    return s.split()[0]

# ALL email IDs per house (AMC + RTA + compliance + branch) from user's original list
EMAILS = {
 "Motilal Oswal":["mfservice@motilaloswal.com","amc@motilaloswal.com","MOTILALMF.customercare@kfintech.com"],
 "quant":["help.investor@quant.in","escalation@quant.in","compliance.mf@quant.in","mfd.north@quant.in","customercare_quant@kfintech.com","QMF.customercare@kfintech.com"],
 "SBI":["partnerforlife@sbimf.com","customer.delight@sbimf.com","enq_sbimf@camsonline.com"],
 "ICICI Prudential":["enquiry@icicipruamc.com"],
 "Invesco":["mfservices@invesco.com","invescomf.Customer@kfintech.com"],
 "HSBC":["investor.line@mutualfunds.hsbc.co.in"],
 "UTI":["service@uti.co.in","UTI@kfintech.com"],
 "Tata":["service@tataamc.com"],
 "Axis":["customerservice@axismf.com","AXISMF.customercare@kfintech.com"],
 "Shriram":["info@shriramamc.in","customercare@shriramamc.co.in"],
 "Kotak":["fundaccops@kotakmutual.in"],
 "Canara Robeco":["crmf@canararobeco.com","CANROBECOMF.customercare@kfintech.com"],
 "HDFC":["hello@hdfcfund.com","shareholders.relations@hdfcfund.com"],
 "Franklin":["services@franklintempleton.com","service@franklintempleton.com","enq_fti@camsonline.com"],
 "Edelweiss":["emfhelp@edelweissmf.com","EDELMF.customercare@kfintech.com"],
 "Nippon India":["customercare@nipponindiaim.in","careershr@nipponindiaim.com"],
 "Bandhan":["investormf@bandhanamc.com","investor.services@bandhanamc.com"],
 "Abakkus":["mf.investor.support@abakkusinvest.com"],
 "Mahindra Manulife":["mfinvestors@mahindra.com","MFINVESTORS@mahindramanulife.com"],
 "Bajaj Finserv":["compliance@bajajamc.com","service@bajajamc.com","partners@bajajamc.com"],
 "LIC":["service@licmf.com","redressal@licmf.com","LICMF.customercare@kfintech.com"],
 "DSP":["service@dspim.com"],
 "Helios":["customercare@helioscapital.in"],
 "Aditya Birla Sun Life":["care.mutualfunds@adityabirlacapital.com"],
 "Mirae Asset":["customercare@miraeasset.com","MIRAEMF.customercare@kfintech.com"],
 "Sundaram":["customerservices@sundarammutual.com","dhirent@sundarammutual.com"],
 "JM":["investor@jmfl.com","JMMF.customercare@kfintech.com"],
 "360 ONE":["mfcompliance@360.one","service@360.one"],
 "NJ":["complianceamc@njgroup.in","customercare@njmutualfund.com"],
 "WhiteOak":["customerservice@whiteoakamc.com","clientservice@whiteoakamc.com"],
 "Zerodha":["compliance@zerodhafundhouse.com","support@zerodhafundhouse.com"],
 "Navi":["mf@navi.com","iro.navimf@navi.com","enq_navi@camsonline.com"],
 "Taurus":["customercare@taurusmutualfund.com","gayathri.ganesan@taurusmutualfund.com","TAURUSMF.customercare@kfintech.com"],
 "Samco":["info@samcomf.com","mfassist@samcomf.com","mfoperations@samco.in"],
 "Bank of India":["service@boimf.in","BAIMF.customercare@kfintech.com"],
 "Baroda BNP Paribas":["service@barodabnpparibasmf.in","cs.barodabnppmf@kfintech.com"],
 "Groww":["iro@growwmf.in","support@growwmf.in"],
 "Union":["investorcare@unionmf.com"],
 "Old Bridge":["services@oldbridgemf.com"],
 "Parag Parikh":["mf@ppfas.com","priyah@ppfas.com"],
 "PGIM":["care@pgimindia.co.in"],
 "Angel One":["customercare@angelonemf.com"],
 "Capitalmind":["help@capitalmindmutual.com"],
 "AlphaGrep":["info@alphagrepmutualfund.com"],
 "JioBlackRock":["care@jioblackrock.com"],
 "Quantum":["customercare@quantumamc.com","QMF.customercare@kfintech.com"],
 "Trust":["investor.service@trustmf.com","puja.trivedi@trustmf.com"],
}
houses = {}
for f in obj.get("folios", []):
    folio = f.get("folio")
    for s in f.get("schemes", []):
        nm = s.get("scheme","?"); h = house_of(nm)
        val = (s.get("valuation") or {})
        houses.setdefault(h, {"schemes":[], "value":0.0, "folios":set()})
        houses[h]["schemes"].append({
            "scheme": nm, "folio": folio, "isin": s.get("isin"),
            "units": s.get("close"), "value": val.get("value"), "amfi": s.get("amfi")})
        houses[h]["value"] += float(val.get("value",0) or 0)
        if folio: houses[h]["folios"].add(folio)

inv = obj.get("investor_info", {}) or {}
providers=[]
for h,d in sorted(houses.items(), key=lambda x:-x[1]["value"]):
    if h in {"THE","Less","Unclaimed"} or d["value"]<1: continue
    providers.append({"house":h, "emails":EMAILS.get(h,[]), "value":round(d["value"],2),
                      "folios":sorted(d["folios"]), "schemes":d["schemes"]})
out={"investor":{"name":inv.get("name"),"address":inv.get("address"),"pan":"OQVPS7357P","email":"whyiswhen@gmail.com"},
     "providers":providers}
json.dump(out, open(r"C:/g/ws/repos/own/life-cli-secrets/mailmerge.json","w"), indent=2)
noemail=[p["house"] for p in providers if not p["emails"]]
print(f"{len(providers)} houses | total emails: {sum(len(p['emails']) for p in providers)} | missing: {noemail}")
print(f"total schemes: {sum(len(p['schemes']) for p in providers)}")
