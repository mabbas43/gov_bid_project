"""FastAPI application."""
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import select

from backend.api import profile, runs, tenders
from backend.config import get_settings
from backend.db import init_db, session_scope
from backend.llm import DeepSeekLLM, LLMError
from backend.models import AgentRun, Tender, utcnow
from backend.seed import upsert_seed_tenders


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    with session_scope() as session:
        # A restart kills background runs: do not leave them looking alive forever.
        for run in session.exec(select(AgentRun).where(AgentRun.status.in_(("queued", "running")))).all():
            run.status, run.error, run.finished_at = "failed", "The server restarted during this run.", utcnow()
            session.add(run)
        session.commit()
        # Demo mode must work on a fresh install, even before `make seed`.
        if session.exec(select(Tender)).first() is None:
            upsert_seed_tenders(session)
    yield


app = FastAPI(title="TenderScout", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(profile.router)
app.include_router(tenders.router)
app.include_router(runs.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/llm-ping")
async def llm_ping() -> dict:
    """Sends 'say OK' to DeepSeek to prove the key works."""
    try:
        llm = DeepSeekLLM()
        reply = await llm.chat([{"role": "user", "content": "say OK"}], max_tokens=5)
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"reply": reply, "model": llm.model, "tokens": llm.usage.total_tokens}
