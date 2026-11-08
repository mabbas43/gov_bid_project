"""Every agent step is written to the AgentStep table as it starts and again when it ends."""
from __future__ import annotations

import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator, Optional

from backend.db import session_scope
from backend.models import AgentStep

MAX_SUMMARY = 500


def clip(text: object, limit: int = MAX_SUMMARY) -> str:
    s = " ".join(str(text).split())
    return s if len(s) <= limit else s[: limit - 1] + "…"


@dataclass
class StepHandle:
    id: int
    output: str = ""
    tokens: int = 0
    thought: str = ""


class StepLogger:
    def __init__(self, run_id: Optional[int] = None):
        self.run_id = run_id
        self._n = 0

    def _next(self) -> int:
        self._n += 1
        return self._n

    def start(self, tool: str, scope: str, input_summary: str, tender_id: Optional[int], thought: str) -> StepHandle:
        with session_scope() as s:
            row = AgentStep(
                run_id=self.run_id,
                step=self._next(),
                scope=scope,
                tool=tool,
                tender_id=tender_id,
                status="running",
                thought_summary=clip(thought, 300),
                input_summary=clip(input_summary),
            )
            s.add(row)
            s.commit()
            return StepHandle(id=row.id, thought=thought)

    def finish(self, handle: StepHandle, status: str, duration_ms: int) -> None:
        with session_scope() as s:
            row = s.get(AgentStep, handle.id)
            row.status = status
            row.output_summary = clip(handle.output)
            row.duration_ms = duration_ms
            row.tokens = handle.tokens
            s.add(row)
            s.commit()

    @asynccontextmanager
    async def step(
        self,
        tool: str,
        scope: str = "analyst",
        input_summary: str = "",
        tender_id: Optional[int] = None,
        thought: str = "",
    ) -> AsyncIterator[StepHandle]:
        handle = self.start(tool, scope, input_summary, tender_id, thought)
        started = time.perf_counter()
        try:
            yield handle
        except Exception as exc:
            handle.output = handle.output or f"{type(exc).__name__}: {exc}"
            self.finish(handle, "error", int((time.perf_counter() - started) * 1000))
            raise
        self.finish(handle, "done", int((time.perf_counter() - started) * 1000))
