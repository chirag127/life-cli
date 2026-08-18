import json
h = json.load(open(r"C:/g/ws/repos/own/life-cli-secrets/holdings.json"))
NOISE = {"THE","Less","Unclaimed","PGIM"}  # PGIM value 1.38 but keep? drop parse-noise only
houses = {k:v for k,v in h["houses"].items() if k not in {"THE","Less","Unclaimed"} and v["value"]>=1.0}

# house -> primary contact email(s). From user's original list + known AMC service IDs.
EMAIL = {
 "Motilal Oswal":"mfservice@motilaloswal.com","quant":"help.investor@quant.in",
 "SBI":"customer.delight@sbimf.com","ICICI Prudential":"enquiry@icicipruamc.com",
 "Invesco":"mfservices@invesco.com","HSBC":"investor.line@mutualfunds.hsbc.co.in",
 "UTI":"service@uti.co.in","Tata":"service@tataamc.com","Axis":"customerservice@axismf.com",
 "Shriram":"info@shriramamc.in","Kotak":"fundaccops@kotakmutual.in",
 "Canara Robeco":"crmf@canararobeco.com","HDFC":"hello@hdfcfund.com",
 "Franklin":"services@franklintempleton.com","Edelweiss":"emfhelp@edelweissmf.com",
 "Nippon India":"customercare@nipponindiaim.in","Bandhan":"investormf@bandhanamc.com",
 "Abakkus":"mf.investor.support@abakkusinvest.com","Mahindra Manulife":"mfinvestors@mahindra.com",
 "Bajaj Finserv":"service@bajajamc.com","LIC":"service@licmf.com","DSP":"service@dspim.com",
 "Helios":"customercare@helioscapital.in","Aditya Birla Sun Life":"care.mutualfunds@adityabirlacapital.com",
 "Mirae Asset":"customercare@miraeasset.com","Sundaram":"customerservices@sundarammutual.com",
 "JM":"investor@jmfl.com","360 ONE":"mfcompliance@360.one","NJ":"customercare@njmutualfund.com",
 "WhiteOak":"customerservice@whiteoakamc.com","Zerodha":"support@zerodhafundhouse.com",
 "Navi":"mf@navi.com","Taurus":"customercare@taurusmutualfund.com","Samco":"info@samcomf.com",
 "Bank of India":"service@boimf.in","Baroda BNP Paribas":"service@barodabnpparibasmf.in",
 "Groww":"iro@growwmf.in","Union":"investorcare@unionmf.com","Old Bridge":"services@oldbridgemf.com",
 "Parag Parikh":"mf@ppfas.com","Angel One":"customercare@angelonemf.com",
 "Capitalmind":"help@capitalmindmutual.com","AlphaGrep":"info@alphagrepmutualfund.com",
 "JioBlackRock":"care@jioblackrock.com","Quantum":"customercare@quantumamc.com",
}
out = []
for hn, d in sorted(houses.items(), key=lambda x:-x[1]["value"]):
    em = EMAIL.get(hn)
    out.append({"house": hn, "email": em, "value": d["value"],
                "schemes": d["schemes"][:5], "n": d["n_schemes"],
                "email_known": bool(em)})
json.dump({"investor": h["investor"], "providers": out},
          open(r"C:/g/ws/repos/own/life-cli-secrets/mailmerge.json","w"), indent=2)
known=[o for o in out if o["email_known"]]; unk=[o for o in out if not o["email_known"]]
print(f"{len(out)} houses to email | {len(known)} have email | {len(unk)} need lookup")
print("\nNEED EMAIL LOOKUP:", [o["house"] for o in unk])
