import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import select

from backend.agent import orchestrator as orch
from backend.agent.demo_llm import DemoLLM
from backend.db import session_scope
from backend.llm import ChatResponse, LLMTimeout, ToolCall, Usage
from backend.main import app
from backend.models import AgentRun, AgentStep, BidPack, Tender
from backend.seed import main as seed_main


def make_run(demo=True, goal="Find IT tenders we can win and bid the best"):
    with session_scope() as s:
        run = AgentRun(goal=goal, demo_mode=demo)
        s.add(run)
        s.commit()
        return run.id


def load(run_id):
    with session_scope() as s:
        run = s.get(AgentRun, run_id)
        steps = s.exec(select(AgentStep).where(AgentStep.run_id == run_id).order_by(AgentStep.id)).all()
    return run, steps


class Scripted:
    """A fake model: replays tool calls and records what it was shown."""

    model = "fake"

    def __init__(self, *turns):
        self.turns = list(turns)
        self.usage = Usage()
        self.seen = []

    async def chat_tools(self, messages, tools, **kw):
        self.seen.append(messages)
        self.usage.add(10, 5)
        turn = self.turns.pop(0)
        if isinstance(turn, Exception):
            raise turn
        if isinstance(turn, str):
            return ChatResponse(content=turn, raw_assistant_message={"role": "assistant", "content": turn})
        name, args = turn
        args = {"thought": f"why {name}", "todo": f"- [ ] after {name}", **args}
        tc = ToolCall(id=f"c{len(self.seen)}", name=name, arguments=args)
        raw = {"role": "assistant", "content": "", "tool_calls": [
            {"id": tc.id, "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}]}
        return ChatResponse(tool_calls=[tc], raw_assistant_message=raw, prompt_tokens=10, completion_tokens=5)


async def test_step_records_model_tokens():
    llm = Scripted(("write_note", {"filename": "n.md", "content": "x"}), "done")
    run_id = make_run()
    await orch.run_agent(run_id, llm=llm)
    _, steps = load(run_id)
    assert steps[0].tokens == 15


async def test_full_demo_loop_end_to_end():
    run_id = make_run()
    await orch.run_agent(run_id)
    run, steps = load(run_id)
    assert run.status == "completed", run.error
    assert "strong fits" in run.final_answer
    top = [s.tool for s in steps if s.scope == "orchestrator"]
    assert top == ["fetch_tender_listings", "download_document", "extract_text", "analyze_many", "write_note", "generate_bid_pack"]
    assert {s.scope for s in steps} == {"orchestrator", "analyst", "bidpack"}
    assert all(s.status == "done" for s in steps)
    assert all(s.thought_summary for s in steps if s.scope == "orchestrator")
    assert run.best_tender_id
    workspace = Path(run.workspace)
    assert (workspace / "todo.md").read_text().count("[x]") == 5
    assert (workspace / "shortlist.md").exists() and (workspace / "listings.json").exists()
    with session_scope() as s:
        pack = s.exec(select(BidPack).where(BidPack.tender_id == run.best_tender_id)).one()
        best = s.get(Tender, run.best_tender_id)
    assert pack.status == "ready" and Path(pack.zip_path).exists()
    assert best.fit_label == "strong"
    assert run.prompt_tokens == 0  # the offline model uses no tokens


async def test_demo_run_never_touches_network(monkeypatch):
    def forbidden(*a, **k):
        raise AssertionError("network client created in demo mode")

    monkeypatch.setattr(orch.collector, "PoliteClient", forbidden)
    monkeypatch.setattr("backend.llm.AsyncOpenAI", forbidden)
    run_id = make_run()
    await orch.run_agent(run_id)
    assert load(run_id)[0].status == "completed"


async def test_todo_is_the_latest_plan_only_and_tender_text_stays_out():
    seed_main()
    with session_scope() as s:
        tid = s.exec(select(Tender).where(Tender.external_id == "SEED-01")).one().id
    llm = Scripted(("fetch_tender_listings", {}), ("analyze_many", {"tender_ids": [tid]}), "done")
    run_id = make_run()
    await orch.run_agent(run_id, llm=llm)
    final = llm.seen[-1]
    anchors = [m for m in final if m["content"].startswith("Current todo.md") ]
    assert len(anchors) == 1 and "after analyze_many" in anchors[0]["content"]
    blob = json.dumps(final)
    assert "SECTION 3. ELIGIBILITY" not in blob  # the document never enters orchestrator context


async def test_large_observation_is_offloaded(tmp_path):
    ctx = orch.RunContext(1, True, tmp_path, DemoLLM(), orch.StepLogger(1))
    big = {"data": "x" * 20_000}
    out = json.loads(orch.reduce_observation(ctx, 3, "tool", big))
    assert Path(out["offloaded_to"]).exists() and len(out["preview"]) == 1500
    assert json.loads(orch.reduce_observation(ctx, 4, "tool", {"a": 1})) == {"a": 1}


async def test_tool_error_goes_back_to_model_and_loop_continues():
    llm = Scripted(("generate_bid_pack", {"tender_id": 9999}), "No suitable tender.")
    run_id = make_run()
    await orch.run_agent(run_id, llm=llm)
    run, steps = load(run_id)
    assert run.status == "completed"
    tool_msgs = [m for m in llm.seen[1] if m["role"] == "tool"]
    assert "error" in json.loads(tool_msgs[0]["content"])
    assert "does not exist" in steps[0].output_summary


async def test_unknown_tool_and_bad_arguments_are_recoverable():
    llm = Scripted(("no_such_tool", {}), ("write_note", {}), "ok")
    run_id = make_run()
    await orch.run_agent(run_id, llm=llm)
    assert load(run_id)[0].status == "completed"


async def test_step_limit():
    llm = Scripted(*[("write_note", {"filename": "n.md", "content": "x"}) for _ in range(30)])
    run_id = make_run()
    await orch.run_agent(run_id, llm=llm)
    run, steps = load(run_id)
    assert run.status == "failed" and "25 step limit" in run.error and len(steps) == 25


async def test_deepseek_timeout_fails_run_cleanly():
    llm = Scripted(("write_note", {"filename": "n.md", "content": "x"}), LLMTimeout("timed out"))
    run_id = make_run()
    await orch.run_agent(run_id, llm=llm)
    run, _ = load(run_id)
    assert run.status == "failed" and "Demo mode" in run.error and run.finished_at


@pytest.mark.parametrize("bad", ["../../etc/passwd", "/etc/passwd"])
async def test_extract_text_cannot_leave_workspace(tmp_path, bad):
    ctx = orch.RunContext(1, True, tmp_path, DemoLLM(), orch.StepLogger(1))
    with pytest.raises(orch.ToolError):
        await orch.tool_extract(ctx, path=bad)


async def test_write_note_cannot_escape_workspace(tmp_path):
    ctx = orch.RunContext(1, True, tmp_path, DemoLLM(), orch.StepLogger(1))
    out = await orch.tool_note(ctx, filename="../../evil.md", content="x")
    assert Path(out["path"]).parent == tmp_path


async def test_demo_cannot_download_from_network(tmp_path):
    ctx = orch.RunContext(1, True, tmp_path, DemoLLM(), orch.StepLogger(1))
    with pytest.raises(orch.ToolError):
        await orch.tool_download(ctx, url="https://epms.ppra.gov.pk/pdf?file=x")


def test_post_run_and_sse_stream():
    with TestClient(app) as c:
        c.put("/settings", json={"demo_mode": True})
        r = c.post("/runs", json={"goal": "Find IT tenders we can win this month and prepare a bid for the best one."})
        assert r.status_code == 202
        run_id = r.json()["id"]
        events = []
        with c.stream("GET", f"/runs/{run_id}/stream") as stream:
            assert stream.headers["content-type"].startswith("text/event-stream")
            name = None
            for line in stream.iter_lines():
                if line.startswith("event: "):
                    name = line[7:]
                elif line.startswith("data: "):
                    events.append((name, json.loads(line[6:])))
        assert events[-1][0] == "end" and events[-1][1]["status"] == "completed"
        steps = [e for n, e in events if n == "step"]
        for key in ("step", "thought_summary", "tool", "status", "duration_ms"):
            assert key in steps[0]
        assert any(s["status"] == "running" for s in steps) or any(s["status"] == "done" for s in steps)
        assert {s["tool"] for s in steps} >= {"fetch_tender_listings", "analyze_many", "generate_bid_pack"}
        tid = events[-1][1]["best_tender_id"]
        got = c.get(f"/tenders/{tid}/bidpack/download")
        assert got.status_code == 200 and got.content[:2] == b"PK"
        assert c.get(f"/runs/{run_id}").json()["status"] == "completed"
        assert c.get("/runs/9999/stream").status_code == 404
