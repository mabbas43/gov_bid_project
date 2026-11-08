import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from backend.agent.orchestrator import run_agent
from backend.db import get_session, session_scope
from backend.models import AgentRun, AgentStep
from backend.settings_service import get_demo_mode

router = APIRouter(tags=["runs"])

POLL_S = 0.25
HEARTBEAT_S = 15
_tasks: set[asyncio.Task] = set()  # strong references, or the loop may collect running tasks


class RunIn(BaseModel):
    goal: str = Field(min_length=3, max_length=2000)


def _run_dict(run: AgentRun) -> dict:
    return {
        "id": run.id, "goal": run.goal, "status": run.status, "demo_mode": run.demo_mode,
        "final_answer": run.final_answer, "error": run.error, "best_tender_id": run.best_tender_id,
        "tokens": run.prompt_tokens + run.completion_tokens,
        "started_at": run.started_at, "finished_at": run.finished_at,
    }


def _step_event(s: AgentStep) -> dict:
    return {
        "id": s.id, "step": s.step, "scope": s.scope, "tool": s.tool, "tender_id": s.tender_id,
        "thought_summary": s.thought_summary, "status": s.status, "duration_ms": s.duration_ms,
        "input_summary": s.input_summary, "output_summary": s.output_summary, "tokens": s.tokens,
    }


@router.post("/runs", status_code=202)
async def start_run(data: RunIn, session: Session = Depends(get_session)) -> dict:
    run = AgentRun(goal=data.goal, demo_mode=get_demo_mode(session))
    session.add(run)
    session.commit()
    session.refresh(run)
    task = asyncio.create_task(run_agent(run.id))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return _run_dict(run)


@router.get("/runs")
def list_runs(session: Session = Depends(get_session)) -> list[dict]:
    rows = session.exec(select(AgentRun).order_by(AgentRun.id.desc()).limit(20)).all()
    return [_run_dict(r) for r in rows]


@router.get("/runs/{run_id}")
def get_run(run_id: int, session: Session = Depends(get_session)) -> dict:
    run = session.get(AgentRun, run_id)
    if run is None:
        raise HTTPException(404, "Run not found")
    steps = session.exec(select(AgentStep).where(AgentStep.run_id == run_id).order_by(AgentStep.id)).all()
    return {**_run_dict(run), "steps": [_step_event(s) for s in steps]}


def _snapshot(run_id: int) -> tuple[dict, list[dict]]:
    with session_scope() as s:
        run = s.get(AgentRun, run_id)
        steps = s.exec(select(AgentStep).where(AgentStep.run_id == run_id).order_by(AgentStep.id)).all()
        return _run_dict(run), [_step_event(x) for x in steps]


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


@router.get("/runs/{run_id}/stream")
async def stream_run(run_id: int, session: Session = Depends(get_session)) -> StreamingResponse:
    """Replays all steps, then sends each change. A reconnecting client just gets the steps again by id."""
    if session.get(AgentRun, run_id) is None:
        raise HTTPException(404, "Run not found")

    async def events():
        seen: dict[int, str] = {}
        idle = 0.0
        while True:
            run, steps = await asyncio.to_thread(_snapshot, run_id)
            changed = False
            for step in steps:
                if seen.get(step["id"]) != step["status"]:
                    seen[step["id"]] = step["status"]
                    changed = True
                    yield _sse("step", step)
            if run["status"] in ("completed", "failed"):
                yield _sse("end", run)
                return
            idle = 0.0 if changed else idle + POLL_S
            if idle >= HEARTBEAT_S:
                idle = 0.0
                yield ": keep-alive\n\n"
            await asyncio.sleep(POLL_S)

    return StreamingResponse(
        events(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
