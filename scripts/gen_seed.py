"""Generates data/seed/ (JSON + tender document per tender + expected labels).

Run once when the seed set changes: backend/.venv/bin/python scripts/gen_seed.py
Clauses are defined once and used for both the document text and the offline extraction, so every
source_quote is guaranteed to appear in its document.
"""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "data" / "seed"


def c(text, type_, threshold=None, mandatory=True, requirement=None):
    return {"text": text, "type": type_, "threshold": threshold, "mandatory": mandatory,
            "requirement": requirement or text}


STD_DOCS = [
    c("Affidavit on stamp paper that the bidder has not been blacklisted by any government body.", "document",
      requirement="Non-blacklisting affidavit"),
    c("Bid security in the form of a pay order or bank guarantee shall accompany the financial bid.", "document",
      requirement="Bid security instrument"),
]
TAX = [
    c("The bidder must hold a valid National Tax Number (NTN) and appear on the FBR Active Taxpayers List (ATL).",
      "registration", "NTN, ATL active", requirement="Valid NTN and active ATL status"),
]

T = [
 dict(id="SEED-01", label="strong", title="Development of Citizen Grievance Portal and Mobile Application",
      agency="Federal Directorate of Public Services", city="Islamabad", value=18_000_000, sec="2% of bid value",
      published=6, closing=24,
      scope=["Design and develop a bilingual (English/Urdu) citizen grievance web portal.",
             "Build Android and iOS mobile apps with complaint tracking and SMS notifications.",
             "Host the solution on cloud infrastructure and provide 12 months of support."],
      keywords="web portal, mobile app, cloud",
      clauses=[*TAX,
        c("The bidder must be a company registered with the Securities and Exchange Commission of Pakistan (SECP).", "registration", "SECP"),
        c("Minimum average annual turnover of PKR 30 million during the last three financial years.", "turnover", "PKR 30 million"),
        c("The bidder must have been in business for at least 3 years.", "experience", "3 years"),
        c("The bidder must have completed at least two similar web or mobile application projects, each worth PKR 5 million or more, for public or private clients.", "experience", "2 similar projects of PKR 5 million", requirement="Two similar web/mobile projects of PKR 5M+"),
        *STD_DOCS]),
 dict(id="SEED-02", label="strong", title="AI Chatbot for Citizen Helpline Services",
      agency="Islamabad Capital Services Cell", city="Islamabad", value=12_000_000, sec="PKR 240,000",
      published=4, closing=18,
      scope=["Deliver an Urdu and English AI chatbot for the citizen helpline on web and WhatsApp.",
             "Integrate the chatbot with the existing complaint database through REST APIs.",
             "Provide an administrator dashboard, staff training and six months of support."],
      keywords="AI chatbot, web, API integration",
      clauses=[*TAX,
        c("The firm must hold valid registration with the Pakistan Software Export Board (PSEB).", "registration", "PSEB"),
        c("Minimum annual turnover of PKR 20 million in the last financial year.", "turnover", "PKR 20 million"),
        c("The bidder must have at least 4 years of business history.", "experience", "4 years"),
        c("The bidder must demonstrate at least one completed AI chatbot or conversational assistant project.", "experience", "1 AI chatbot project", requirement="One completed AI chatbot project"),
        *STD_DOCS]),
 dict(id="SEED-03", label="strong", title="Migration of Statistical Data Systems to Cloud Infrastructure",
      agency="National Bureau of Survey Data", city="Islamabad", value=25_000_000, sec="2% of bid value",
      published=7, closing=30,
      scope=["Migrate twelve on-premise statistical applications to AWS or Azure.",
             "Implement backup, monitoring, identity management and disaster recovery.",
             "Transfer knowledge to in-house staff and support operations for one year."],
      keywords="cloud migration, AWS, Azure",
      clauses=[*TAX,
        c("The bidder must be registered with SECP as a private or public limited company.", "registration", "SECP"),
        c("Minimum average annual turnover of PKR 40 million over the last three years.", "turnover", "PKR 40 million"),
        c("The firm must have a minimum of 5 years in business.", "experience", "5 years"),
        c("The bidder must have completed at least one cloud migration project on AWS or Azure.", "experience", "1 cloud migration project", requirement="One completed cloud migration project"),
        *STD_DOCS]),
 dict(id="SEED-04", label="strong", title="Campus Network Upgrade (LAN/WAN and Wi-Fi)",
      agency="Federal College of Technical Education", city="Rawalpindi", value=20_000_000, sec="2% of bid value",
      published=3, closing=21,
      scope=["Upgrade the campus LAN and WAN, including structured cabling across six blocks.",
             "Install managed switches, firewalls and campus-wide Wi-Fi.",
             "Provide network monitoring, documentation and a one year warranty."],
      keywords="network, LAN, WAN, Wi-Fi",
      clauses=[*TAX,
        c("Minimum annual turnover of PKR 25 million during the last financial year.", "turnover", "PKR 25 million"),
        c("The bidder must have been in business for at least 3 years.", "experience", "3 years"),
        c("The bidder must have completed at least one network infrastructure project worth PKR 10 million or more.", "experience", "1 network project of PKR 10 million", requirement="One network project of PKR 10M+"),
        *STD_DOCS]),

 dict(id="SEED-05", label="partial", title="Enterprise Resource Planning (ERP) System for Education Foundation",
      agency="Provincial Education Foundation", city="Lahore", value=95_000_000, sec="2% of bid value",
      published=5, closing=27,
      scope=["Implement finance, HR, payroll and procurement ERP modules.",
             "Migrate legacy accounting data and integrate with the provincial treasury system.",
             "Provide on-site implementation across nine regional offices."],
      keywords="ERP, finance, payroll",
      clauses=[*TAX,
        c("Minimum average annual turnover of PKR 40 million over the last three years.", "turnover", "PKR 40 million"),
        c("The bidder must have been in business for at least 5 years.", "experience", "5 years"),
        c("Prior ERP implementation experience at two public sector organizations is preferred and carries additional marks.", "experience", "2 ERP implementations", False, "Preferred: two public sector ERP implementations"),
        c("SAP or Oracle partner certification is desirable.", "technical", "SAP or Oracle partner", False, "Desirable: SAP or Oracle partner certification"),
        c("The bidder should deploy a team of at least 25 full-time technical staff on this assignment.", "technical", "25 staff", False, "Preferred: 25 full-time technical staff"),
        *STD_DOCS]),
 dict(id="SEED-06", label="partial", title="Security Operations Centre and Data Centre Hardening",
      agency="Directorate of Government Information Security", city="Islamabad", value=60_000_000, sec="2.5% of bid value",
      published=8, closing=20,
      scope=["Establish a 24x7 Security Operations Centre with SIEM and SOAR tooling.",
             "Harden data centre servers and storage, and conduct penetration testing.",
             "Supply network security appliances with three year OEM support."],
      keywords="cybersecurity, SOC, SIEM",
      clauses=[*TAX,
        c("Minimum average annual turnover of PKR 45 million over the last three years.", "turnover", "PKR 45 million"),
        c("The bidder must hold a valid ISO 27001 certificate.", "technical", "ISO 27001", True, "Valid ISO 27001 certification"),
        c("At least two staff members must hold CISSP or CISM certifications.", "technical", "2 CISSP/CISM staff", True, "Two CISSP or CISM certified staff"),
        c("Authorized OEM partner letter for the proposed SIEM is required.", "technical", "SIEM OEM letter", True, "OEM authorization letter for SIEM"),
        *STD_DOCS]),
 dict(id="SEED-07", label="partial", title="Digitization of Land Revenue Records",
      agency="Punjab Land Records Cell", city="Lahore", value=32_000_000, sec="2% of bid value",
      published=2, closing=25,
      scope=["Scan and index 400,000 land revenue records with data entry and quality control.",
             "Build a records search web application for revenue offices.",
             "Run the scanning operation on site at two district record rooms."],
      keywords="digitization, scanning, web application",
      clauses=[*TAX,
        c("Minimum annual turnover of PKR 30 million during the last financial year.", "turnover", "PKR 30 million"),
        c("The bidder must have an office in Punjab, or submit an undertaking to establish one within 30 days of contract award.", "location", "Punjab office or undertaking", True, "Punjab office, or undertaking to open one"),
        c("The bidder should have digitized at least one million physical records in past assignments.", "experience", "1 million records digitized", False, "Preferred: one million records digitized"),
        c("Experience with land revenue systems will be an added advantage.", "experience", "land revenue systems", False, "Preferred: land revenue system experience"),
        *STD_DOCS]),
 dict(id="SEED-08", label="partial", title="Hospital Management Information System",
      agency="KP Health Facilities Authority", city="Peshawar", value=48_000_000, sec="2% of bid value",
      published=9, closing=16,
      scope=["Develop a Hospital Management Information System for four tertiary hospitals.",
             "Cover patient registration, pharmacy, laboratory and billing modules.",
             "Provide on-site support at each hospital for twelve months."],
      keywords="HMIS, web application, health",
      clauses=[*TAX,
        c("Minimum average annual turnover of PKR 50 million over the last three years.", "turnover", "PKR 50 million"),
        c("The bidder must have been in business for at least 5 years.", "experience", "5 years"),
        c("HL7 or FHIR integration capability must be demonstrated in the technical proposal.", "technical", "HL7 or FHIR", True, "Demonstrated HL7/FHIR integration capability"),
        c("Prior HMIS deployment in a tertiary care hospital is preferred.", "experience", "tertiary HMIS deployment", False, "Preferred: tertiary hospital HMIS deployment"),
        c("A registered office in Khyber Pakhtunkhwa is preferred.", "location", "Khyber Pakhtunkhwa office", False, "Preferred: registered office in KP"),
        *STD_DOCS]),

 dict(id="SEED-09", label="non_fit", title="Nationwide Fibre Optic Backbone for Government Network",
      agency="National Government Connectivity Company", city="Islamabad", value=2_400_000_000, sec="5% of bid value",
      published=10, closing=35,
      scope=["Lay 3,000 km of fibre optic backbone connecting federal and provincial offices.",
             "Supply and commission DWDM and core routing equipment.",
             "Operate and maintain the network for five years."],
      keywords="fibre, network, telecom",
      clauses=[*TAX,
        c("Minimum average annual turnover of PKR 500 million over the last three years.", "turnover", "PKR 500 million"),
        c("The bidder must have been in business for at least 10 years.", "experience", "10 years"),
        *STD_DOCS]),
 dict(id="SEED-10", label="non_fit", title="Construction of Government IT Park Building",
      agency="Federal Public Works Authority", city="Islamabad", value=850_000_000, sec="5% of bid value",
      published=6, closing=28,
      scope=["Construct a seven-storey IT park building including civil, electrical and HVAC works.",
             "Provide raised flooring and server room civil works.",
             "Complete construction within 24 months."],
      keywords="construction, civil works",
      clauses=[*TAX,
        c("The contractor must hold a valid Pakistan Engineering Council (PEC) registration in category C-3 or above for civil works.", "registration", "PEC C-3 civil", True, "PEC C-3 or above registration (civil)"),
        c("Minimum annual turnover of PKR 300 million in the last financial year.", "turnover", "PKR 300 million"),
        *STD_DOCS]),
 dict(id="SEED-11", label="non_fit", title="Sindh Municipal Services Web Portal",
      agency="Sindh Municipal Services Board", city="Karachi", value=15_000_000, sec="2% of bid value",
      published=3, closing=19,
      scope=["Develop a municipal services web portal for water, sanitation and property tax.",
             "Provide on-site support at the Board's offices.",
             "Train municipal staff and maintain the portal for one year."],
      keywords="web portal, municipal",
      clauses=[*TAX,
        c("Minimum annual turnover of PKR 15 million in the last financial year.", "turnover", "PKR 15 million"),
        c("The bidder must have a registered head office in Karachi at the time of bid submission. Bids from firms without a Karachi office shall be rejected.", "location", "Karachi office", True, "Registered head office in Karachi"),
        *STD_DOCS]),
 dict(id="SEED-12", label="non_fit", title="Core Banking System Replacement",
      agency="Public Sector Development Bank", city="Karachi", value=1_200_000_000, sec="5% of bid value",
      published=11, closing=40,
      scope=["Replace the core banking platform across 150 branches.",
             "Migrate customer accounts and integrate with national payment switches.",
             "Provide 24x7 production support for three years."],
      keywords="core banking",
      clauses=[*TAX,
        c("The bidder must have a minimum of 15 years in business.", "experience", "15 years"),
        c("Minimum average annual turnover of PKR 750 million over the last three years.", "turnover", "PKR 750 million"),
        c("The bidder must have implemented core banking at no fewer than three commercial banks.", "experience", "3 core banking implementations", True, "Core banking at three commercial banks"),
        *STD_DOCS]),
]

DOC = """SAMPLE DOCUMENT FOR DEMONSTRATION. NOT A REAL TENDER.

{agency}
{city}, Pakistan

BIDDING DOCUMENT
{title}
Tender Reference No: {id}

Procurement method: Single Stage, Two Envelope, under the Public Procurement Rules 2004.
Bids shall be submitted through the e-Pak Acquisition and Disposal System (e-PADS).

Date of publication: {{{{PUBLISHED_DATE}}}}
Closing date and time: {{{{CLOSING_DATE}}}} at 11:00 AM
Bids will be opened 30 minutes after the closing time.

SECTION 1. INVITATION FOR BIDS
{agency} invites sealed bids from eligible firms for the assignment described below.
The estimated cost of the assignment is PKR {value:,}.

SECTION 2. SCOPE OF WORK
{scope}

SECTION 3. ELIGIBILITY CRITERIA
{clauses}

SECTION 4. BID SECURITY
Bid security of {sec} shall be furnished. Bids without bid security shall be rejected.
Bid validity shall be 120 days from the date of opening.

SECTION 5. EVALUATION
The technical proposal carries 70 marks and the minimum qualifying score is 65%.
Financial proposals of technically responsive bidders only will be opened.
Award shall be made to the most advantageous bid under Rule 38 of the Public Procurement Rules 2004.

SECTION 6. CONTRACT TERMS
Performance guarantee: 10% of contract value. Payment is milestone based.
Applicable taxes shall be deducted at source as per rules.
"""

OUT.mkdir(parents=True, exist_ok=True)
labels = {}
for t in T:
    doc = DOC.format(
        agency=t["agency"], city=t["city"], title=t["title"], id=t["id"], value=t["value"], sec=t["sec"],
        scope="\n".join(f"{i}. {s}" for i, s in enumerate(t["scope"], 1)),
        clauses="\n".join(f"3.{i} {cl['text']}" for i, cl in enumerate(t["clauses"], 1)),
    )
    (OUT / f"{t['id']}.txt").write_text(doc)
    record = {
        "external_id": t["id"], "title": t["title"], "agency": t["agency"], "city": t["city"],
        "published_days_ago": t["published"], "closing_in_days": t["closing"], "document": f"{t['id']}.txt",
        "demo_extraction": {
            "scope_summary": " ".join(t["scope"]),
            "estimated_value_pkr": t["value"],
            "bid_security": t["sec"],
            "eligibility": [
                {"requirement": cl["requirement"], "type": cl["type"], "threshold": cl["threshold"],
                 "mandatory": cl["mandatory"], "source_quote": cl["text"]} for cl in t["clauses"]
            ],
        },
    }
    (OUT / f"{t['id']}.json").write_text(json.dumps(record, indent=2) + "\n")
    labels[t["id"]] = t["label"]
(OUT / "expected_labels.json").write_text(json.dumps(labels, indent=2) + "\n")
print(f"Wrote {len(T)} tenders to {OUT}")
