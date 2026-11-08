import re
import zipfile
from datetime import date, timedelta
from pathlib import Path

import pytest
from docx import Document
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from sqlmodel import select

from backend.agent import bidpack as bp
from backend.agent.analyst import analyze_many
from backend.agent.demo_llm import DemoLLM
from backend.db import session_scope
from backend.llm import LLMError, Usage
from backend.main import app
from backend.models import Tender
from backend.profile_service import DEFAULT_PROFILE
from backend.seed import main as seed_main


async def analysed(external_id="SEED-01"):
    seed_main()
    with session_scope() as s:
        tid = s.exec(select(Tender).where(Tender.external_id == external_id)).one().id
    await analyze_many([tid], DemoLLM)
    return tid


async def test_zip_has_all_documents():
    tid = await analysed()
    pack = await bp.generate_bid_pack(tid)
    assert pack.status == "ready" and pack.generation_ms >= 0
    assert Path(pack.zip_path).name == f"bidpack_{tid}.zip"
    with zipfile.ZipFile(pack.zip_path) as zf:
        assert sorted(zf.namelist()) == sorted(bp.FILES) and zf.testzip() is None


async def test_compliance_checklist_rows_and_formatting():
    tid = await analysed("SEED-11")
    pack = await bp.generate_bid_pack(tid)
    ws = load_workbook(Path(pack.zip_path).parent / "compliance_checklist.xlsx").active
    headers = [c.value for c in ws[4]]
    for h in ("Requirement", "Our status", "Document needed", "Owner", "Notes"):
        assert h in headers
    statuses = [ws.cell(row=r, column=6).value for r in range(5, ws.max_row + 1)]
    assert "FAIL" in statuses and "PASS" in statuses and "UNCLEAR" in statuses
    formulas = [r.formula[0] for rng in ws.conditional_formatting for r in rng.rules]
    assert {'$F5="PASS"', '$F5="FAIL"', '$F5="UNCLEAR"'} <= set(formulas)


async def test_cost_estimate_uses_formulas_that_compute():
    tid = await analysed()
    pack = await bp.generate_bid_pack(tid)
    wb = load_workbook(Path(pack.zip_path).parent / "cost_estimate.xlsx")
    ws, notes = wb["Cost Estimate"], wb["Assumptions"]
    rows = {ws.cell(row=r, column=2).value: r for r in range(5, ws.max_row + 1)}
    sub, tax, total = rows["Subtotal"], rows["Sales tax (18%)"], rows["Grand total"]
    assert str(ws.cell(row=sub, column=6).value).startswith("=SUM(F5:")
    assert ws.cell(row=tax, column=6).value == f"=F{sub}*Assumptions!B4"
    assert ws.cell(row=total, column=6).value == f"=F{sub}+F{tax}"
    assert notes["B4"].value == 0.18
    for r in range(5, sub):
        assert ws.cell(row=r, column=6).value == f"=D{r}*E{r}"
    # Evaluate: the total should land near 90% of the agency's estimate.
    subtotal = sum(ws.cell(row=r, column=4).value * ws.cell(row=r, column=5).value for r in range(5, sub))
    grand = subtotal * 1.18
    assert 0.8 * 18_000_000 < grand < 18_000_000


async def test_proposal_sections_and_only_real_projects():
    tid = await analysed()
    pack = await bp.generate_bid_pack(tid)
    doc = Document(Path(pack.zip_path).parent / "technical_proposal.docx")
    headings = [p.text for p in doc.paragraphs if p.style.name.startswith("Heading")]
    for name in ("Understanding of Scope", "Approach and Methodology", "Work Plan", "Team Structure", "Relevant Experience", "Assumptions"):
        assert any(name in h for h in headings), name
    assert any("TECHNICAL PROPOSAL" in p.text for p in doc.paragraphs[:10])
    assert len(doc.tables) == 3
    listed = {row.cells[0].text for row in doc.tables[2].rows[1:]}
    assert listed == {p.title for p in DEFAULT_PROFILE.past_projects}


async def test_risk_register_flags_disqualifier():
    tid = await analysed("SEED-09")
    pack = await bp.generate_bid_pack(tid)
    ws = load_workbook(Path(pack.zip_path).parent / "risk_register.xlsx").active
    rows = [[c.value for c in r] for r in ws.iter_rows(min_row=5)]
    assert any(r[1] == "Disqualifier" and r[2] == "High" and "Turnover" in r[3] for r in rows)
    assert all(r[4] for r in rows)  # every risk has a mitigation


async def test_near_deadline_is_a_risk():
    tid = await analysed()
    with session_scope() as s:
        t = s.get(Tender, tid)
        t.closing_date = date.today() + timedelta(days=3)
        s.add(t)
        s.commit()
    pack = await bp.generate_bid_pack(tid)
    ws = load_workbook(Path(pack.zip_path).parent / "risk_register.xlsx").active
    assert any(r[1].value == "Deadline" for r in ws.iter_rows(min_row=5))


async def test_requires_analysis_first():
    seed_main()
    with session_scope() as s:
        tid = s.exec(select(Tender).where(Tender.external_id == "SEED-02")).one().id
    with pytest.raises(bp.BidPackError):
        await bp.generate_bid_pack(tid)


class BrokenLLM:
    usage = Usage()

    async def chat_json(self, *a, **k):
        raise LLMError("down")


async def test_llm_failure_falls_back_to_template():
    tid = await analysed()
    pack = await bp.generate_bid_pack(tid, BrokenLLM())
    assert pack.status == "ready"


async def test_empty_requirements_and_no_value_still_builds():
    tid = await analysed()
    with session_scope() as s:
        t = s.get(Tender, tid)
        t.estimated_value_pkr = None
        s.add(t)
        s.commit()
        from backend.models import EligibilityCheck
        for c in s.exec(select(EligibilityCheck).where(EligibilityCheck.tender_id == tid)).all():
            s.delete(c)
        s.commit()
    pack = await bp.generate_bid_pack(tid)
    assert pack.status == "ready"
    notes = load_workbook(Path(pack.zip_path).parent / "cost_estimate.xlsx")["Assumptions"]
    assert "placeholder" in notes["A8"].value


def test_api_endpoints():
    with TestClient(app) as c:
        c.put("/settings", json={"demo_mode": True})
        seed_main()
        rows = c.get("/tenders").json()
        assert len(rows) == 12
        tid = rows[0]["id"]
        assert c.post(f"/tenders/{tid}/bidpack").status_code == 409  # not analysed yet
        assert c.post(f"/tenders/{tid}/analyze").json()["status"] == "analyzed"
        created = c.post(f"/tenders/{tid}/bidpack")
        assert created.status_code == 200 and created.json()["generation_ms"] is not None
        assert c.get(f"/tenders/{tid}/bidpack").json()["status"] == "ready"
        got = c.get(f"/tenders/{tid}/bidpack/download")
        assert got.content[:2] == b"PK" and "bidpack_" in got.headers["content-disposition"]
        assert c.get(f"/tenders/{tid}/bidpack/files/risk_register.xlsx").status_code == 200
        assert c.get(f"/tenders/{tid}/bidpack/files/secret.txt").status_code == 404
        assert c.get("/tenders/9999").status_code == 404
        kpi = c.get("/dashboard").json()
        assert kpi["tenders_scanned"] == 1 and kpi["avg_bidpack_ms"] is not None
        detail = c.get(f"/tenders/{tid}").json()
        assert detail["checks"] and detail["bid_pack"]["status"] == "ready"
