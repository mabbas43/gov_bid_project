import json
import re

from fastapi.testclient import TestClient
from sqlmodel import select

from backend.config import get_settings
from backend.db import session_scope
from backend.main import app
from backend.models import Tender
from backend.seed import expected_labels, main as seed_main, seed_records


def test_default_profile_matches_brief():
    with TestClient(app) as c:
        p = c.get("/profile").json()
    assert p["city"] == "Islamabad" and p["team_size"] == 20
    assert p["annual_turnover_pkr"] == 50_000_000 and p["years_in_business"] == 6
    assert p["registrations"]["atl_status"] == "active"


def test_profile_update_round_trip():
    with TestClient(app) as c:
        p = c.get("/profile").json()
        p["team_size"] = 25
        p["past_projects"].append({"title": "X", "client": "Y", "value_pkr": 1, "year": 2026})
        assert c.put("/profile", json=p).status_code == 200
        got = c.get("/profile").json()
    assert got["team_size"] == 25 and got["past_projects"][-1]["title"] == "X"


def test_profile_rejects_invalid():
    with TestClient(app) as c:
        p = c.get("/profile").json()
        p["team_size"] = 0
        assert c.put("/profile", json=p).status_code == 422


def test_seed_mix_and_labels():
    labels = expected_labels()
    assert len(labels) == 12
    assert sorted(labels.values()).count("strong") == 4
    assert sorted(labels.values()).count("partial") == 4
    assert sorted(labels.values()).count("non_fit") == 4
    assert {r["external_id"] for r in seed_records()} == set(labels)


def test_every_source_quote_is_in_its_document():
    for rec in seed_records():
        doc = (get_settings().seed_dir / rec["document"]).read_text()
        for req in rec["demo_extraction"]["eligibility"]:
            assert req["source_quote"] in doc, (rec["external_id"], req["source_quote"])


def test_seed_is_idempotent_with_future_dates():
    seed_main()
    seed_main()
    with session_scope() as s:
        rows = s.exec(select(Tender)).all()
    assert len(rows) == 12
    for t in rows:
        text = open(t.text_path).read()
        assert "{{" not in text
        assert t.closing_date.isoformat() in text
        assert re.search(r"Tender Reference No: SEED-\d\d", text)
