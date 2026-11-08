from datetime import date
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from backend.agent import bidpack as bp
from backend.agent.analyst import analyze_many
from backend.agent.llm_factory import get_llm
from backend.db import get_session
from backend.llm import LLMError
from backend.models import BidPack, EligibilityCheck, Tender
from backend.settings_service import get_demo_mode, set_demo_mode

router = APIRouter(tags=["tenders"])


class SettingsIn(BaseModel):
    demo_mode: bool


def _pack_dict(pack: Optional[BidPack]) -> Optional[dict]:
    if pack is None:
        return None
    return {
        "status": pack.status,
        "files": pack.files,
        "generation_ms": pack.generation_ms,
        "error": pack.error,
        "created_at": pack.created_at,
    }


def _summary(t: Tender) -> dict:
    days = (t.closing_date - date.today()).days if t.closing_date else None
    return {
        "id": t.id, "external_id": t.external_id, "title": t.title, "agency": t.agency, "source": t.source,
        "status": t.status, "status_detail": t.status_detail, "published_date": t.published_date,
        "closing_date": t.closing_date, "days_to_close": days, "estimated_value_pkr": t.estimated_value_pkr,
        "fit_score": t.fit_score, "fit_label": t.fit_label, "fit_reason": t.fit_reason,
    }


def _visible(session: Session) -> list[Tender]:
    """Sample and real tenders never mix: demo mode shows seeds, live mode shows real ones.

    Live mode shows seeds only when there are no real tenders, such as after a PPRA fallback.
    """
    rows = list(session.exec(select(Tender)).all())
    seeds = [t for t in rows if t.source == "seed"]
    if get_demo_mode(session):
        return seeds
    return [t for t in rows if t.source != "seed"] or seeds


@router.get("/tenders")
def list_tenders(session: Session = Depends(get_session)) -> list[dict]:
    rows = sorted(_visible(session), key=lambda t: -(t.fit_score if t.fit_score is not None else -1))
    return [_summary(t) for t in rows]


@router.get("/tenders/{tender_id}")
def get_tender(tender_id: int, session: Session = Depends(get_session)) -> dict:
    t = session.get(Tender, tender_id)
    if t is None:
        raise HTTPException(404, "Tender not found")
    checks = session.exec(select(EligibilityCheck).where(EligibilityCheck.tender_id == tender_id)).all()
    return {
        **_summary(t),
        "document_url": t.document_url,
        "scope_summary": t.scope_summary,
        "bid_security": t.bid_security,
        "score_breakdown": t.score_breakdown,
        "checks": [c.model_dump(exclude={"tender_id"}) for c in checks],
        "bid_pack": _pack_dict(bp.latest_pack(session, tender_id)),
    }


@router.post("/tenders/{tender_id}/analyze")
async def analyze_tender(tender_id: int, session: Session = Depends(get_session)) -> dict:
    if session.get(Tender, tender_id) is None:
        raise HTTPException(404, "Tender not found")
    demo = get_demo_mode(session)
    try:
        outcome = (await analyze_many([tender_id], lambda: get_llm(demo)))[0]
    except LLMError as exc:
        raise HTTPException(502, str(exc)) from exc
    return {"status": outcome.status, "score": outcome.score, "label": outcome.label, "reason": outcome.reason}


@router.post("/tenders/{tender_id}/bidpack")
async def create_bidpack(tender_id: int, session: Session = Depends(get_session)) -> dict:
    if session.get(Tender, tender_id) is None:
        raise HTTPException(404, "Tender not found")
    demo = get_demo_mode(session)
    llm = None
    if not demo:
        try:
            llm = get_llm(False)
        except LLMError:
            llm = None  # no key: the template still produces a complete pack
    try:
        pack = await bp.generate_bid_pack(tender_id, llm)
    except bp.BidPackError as exc:
        raise HTTPException(409, str(exc)) from exc
    return _pack_dict(pack)


def _ready_pack(session: Session, tender_id: int) -> BidPack:
    pack = bp.latest_pack(session, tender_id)
    if pack is None or pack.status != "ready":
        raise HTTPException(404, "No bid pack has been generated for this tender")
    return pack


@router.get("/tenders/{tender_id}/bidpack")
def read_bidpack(tender_id: int, session: Session = Depends(get_session)) -> dict:
    return _pack_dict(_ready_pack(session, tender_id))


@router.get("/tenders/{tender_id}/bidpack/download")
def download_bidpack(tender_id: int, session: Session = Depends(get_session)) -> FileResponse:
    pack = _ready_pack(session, tender_id)
    return FileResponse(pack.zip_path, media_type="application/zip", filename=Path(pack.zip_path).name)


@router.get("/tenders/{tender_id}/bidpack/files/{name}")
def download_bidpack_file(tender_id: int, name: str, session: Session = Depends(get_session)) -> FileResponse:
    pack = _ready_pack(session, tender_id)
    if name not in pack.files:  # allowlist: blocks path traversal
        raise HTTPException(404, "No such file in this bid pack")
    return FileResponse(Path(pack.zip_path).parent / name, filename=name)


@router.get("/dashboard")
def dashboard(session: Session = Depends(get_session)) -> dict:
    rows = _visible(session)
    today = date.today()
    analyzed = [t for t in rows if t.fit_score is not None]
    strong = [t for t in analyzed if t.fit_score >= 70]
    upcoming = [t for t in analyzed if t.fit_score >= 30 and t.closing_date and t.closing_date >= today]
    nearest = min(upcoming, key=lambda t: t.closing_date, default=None)
    ids = {t.id for t in rows}
    packs = [
        p.generation_ms for p in session.exec(select(BidPack).where(BidPack.status == "ready")).all()
        if p.tender_id in ids and p.generation_ms is not None
    ]
    return {
        "tenders_scanned": len(analyzed),
        "tenders_total": len(rows),
        "strong_fits": len(strong),
        "total_fit_value_pkr": sum(t.estimated_value_pkr or 0 for t in strong),
        "nearest_deadline": {
            "tender_id": nearest.id, "title": nearest.title, "closing_date": nearest.closing_date,
            "days_to_close": (nearest.closing_date - today).days,
        } if nearest else None,
        "avg_bidpack_ms": round(sum(packs) / len(packs)) if packs else None,
        "demo_mode": get_demo_mode(session),
    }


@router.get("/settings")
def read_settings(session: Session = Depends(get_session)) -> dict:
    return {"demo_mode": get_demo_mode(session)}


@router.put("/settings")
def write_settings(data: SettingsIn, session: Session = Depends(get_session)) -> dict:
    return {"demo_mode": set_demo_mode(session, data.demo_mode)}
