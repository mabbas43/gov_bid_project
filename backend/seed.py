"""Loads data/seed/ into the database (make seed). Idempotent: seed tenders are reset each time.

Dates in the seed are relative so the demo never goes stale: closing dates are computed at load time.
"""
import json
from datetime import date, timedelta
from pathlib import Path

from sqlmodel import Session, select

from backend.config import get_settings
from backend.db import init_db, session_scope
from backend.models import BidPack, EligibilityCheck, Tender
from backend.profile_service import get_or_create_profile


def seed_records() -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted(get_settings().seed_dir.glob("SEED-*.json"))]


def expected_labels() -> dict[str, str]:
    return json.loads((get_settings().seed_dir / "expected_labels.json").read_text())


def render_document(rec: dict) -> Path:
    """Fills date placeholders and writes the document to the shared seed workspace."""
    settings = get_settings()
    today = date.today()
    out_dir = settings.workspace_dir / "seed"
    out_dir.mkdir(parents=True, exist_ok=True)
    text = (settings.seed_dir / rec["document"]).read_text()
    text = text.replace("{{PUBLISHED_DATE}}", (today - timedelta(days=rec["published_days_ago"])).isoformat())
    text = text.replace("{{CLOSING_DATE}}", (today + timedelta(days=rec["closing_in_days"])).isoformat())
    path = out_dir / rec["document"]
    path.write_text(text)
    return path


def upsert_seed_tenders(session: Session, reset: bool = True) -> list[Tender]:
    today = date.today()
    tenders = []
    for rec in seed_records():
        row = session.exec(select(Tender).where(Tender.external_id == rec["external_id"])).first()
        if row is None:
            row = Tender(external_id=rec["external_id"], title=rec["title"], source="seed")
        elif reset:
            for model in (EligibilityCheck, BidPack):
                for old in session.exec(select(model).where(model.tender_id == row.id)).all():
                    session.delete(old)
            row.status, row.status_detail = "new", None
            row.fit_score = row.fit_label = row.fit_reason = row.scope_summary = None
            row.estimated_value_pkr = row.bid_security = row.analyzed_at = None
            row.requirements, row.score_breakdown = [], {}
        row.title = rec["title"]
        row.agency = rec["agency"]
        row.published_date = today - timedelta(days=rec["published_days_ago"])
        row.closing_date = today + timedelta(days=rec["closing_in_days"])
        row.text_path = str(render_document(rec))
        session.add(row)
        tenders.append(row)
    session.commit()
    for row in tenders:
        session.refresh(row)
    return tenders


def main() -> None:
    init_db()
    with session_scope() as session:
        get_or_create_profile(session)
        tenders = upsert_seed_tenders(session)
    print(f"Seeded {len(tenders)} tenders and the company profile.")


def analyze_offline() -> None:
    """Fills the dashboard using the offline demo pipeline, so it is not empty on first open."""
    import asyncio

    from backend.agent.analyst import analyze_many
    from backend.agent.demo_llm import DemoLLM

    with session_scope() as session:
        ids = [t.id for t in session.exec(select(Tender).where(Tender.source == "seed")).all()]

    def fast() -> DemoLLM:
        llm = DemoLLM()
        llm._pause = _no_pause  # type: ignore[method-assign]
        return llm

    outcomes = asyncio.run(analyze_many(ids, fast))
    print(f"Analysed {len(outcomes)} seed tenders offline (demo pipeline, no model used).")


async def _no_pause(_fraction: float = 1.0) -> None:
    return None


if __name__ == "__main__":
    main()
    analyze_offline()
