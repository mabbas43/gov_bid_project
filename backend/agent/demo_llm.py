"""Offline stand-in for DeepSeek used when DEMO_MODE is on. Makes no network calls and uses no tokens.

It returns canned seed extractions and a scripted tool sequence, so a demo run shows the real pipeline
(rules, scoring, persistence, bid pack) but says nothing about model accuracy. `make eval` uses DeepSeek.
"""
from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Type, TypeVar

from pydantic import BaseModel

from backend.agent.rules import parse_pkr
from backend.config import get_settings
from backend.llm import ChatResponse, ToolCall, Usage
from backend.schemas import ChunkSummary, Extraction, FuzzyBatch, FuzzyItem
from backend.seed import seed_records

T = TypeVar("T", bound=BaseModel)

_DOMAIN_TERMS = {
    "web": ["web", "portal", "website"],
    "mobile": ["mobile", "app"],
    "chatbot": ["chatbot", "conversational"],
    "cloud": ["cloud", "aws", "azure"],
    "network": ["network", "lan", "wan"],
    "erp": ["erp"],
    "digitiz": ["digitiz", "digitis"],
    "land": ["land revenue"],
    "hmis": ["hmis"],
    "banking": ["core banking"],
}
_NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}


def _required_count(text: str) -> int:
    lowered = text.lower()
    m = re.search(r"\b(\d+)\b(?=[^.]*(?:project|implementation|deployment|record))", lowered)
    if m:
        return int(m.group(1))
    for word, n in _NUMBER_WORDS.items():
        if re.search(rf"\b{word}\b", lowered):
            return n
    return 1


def fuzzy_verdict(item: dict, projects: list[dict]) -> FuzzyItem:
    """Heuristic judgement over past_projects: counts matches by domain and value."""
    index = item["index"]
    text = f"{item.get('requirement', '')} {item.get('threshold') or ''}"
    lowered = text.lower()
    wanted = [d for d, terms in _DOMAIN_TERMS.items() if any(t in lowered for t in terms)]
    if not wanted:
        return FuzzyItem(index=index, status="unclear", reason="The profile does not mention this; confirm manually.")
    floor = parse_pkr(item.get("threshold")) or 0
    matches = [
        p for p in projects
        if p["value_pkr"] >= floor
        and any(t in p["title"].lower() for d in wanted for t in _DOMAIN_TERMS[d])
    ]
    needed = _required_count(text)
    names = ", ".join(p["title"] for p in matches) or "none"
    if len(matches) >= needed:
        return FuzzyItem(index=index, status="pass", reason=f"{len(matches)} matching past project(s): {names}.")
    return FuzzyItem(index=index, status="fail", reason=f"Needs {needed}; profile lists {len(matches)} matching ({names}).")


def _scripted_plan(messages: list[dict]) -> ChatResponse:
    done = [m.get("name") for m in messages if m.get("role") == "tool"]
    last = next((m for m in reversed(messages) if m.get("role") == "tool"), None)
    observation = _parse_observation(last["content"]) if last else {}

    def todo(*finished: str) -> str:
        steps = [
            "Fetch current IT tender listings", "Download a sample tender document", "Extract its text",
            "Analyse all tenders with isolated sub-agents", "Record the shortlist",
            "Generate the bid pack for the best tender",
        ]
        return "\n".join(f"- [{'x' if s in finished else ' '}] {s}" for s in steps)

    def call(name: str, thought: str, finished: tuple[str, ...], **args: Any) -> ChatResponse:
        args |= {"thought": thought, "todo": todo(*finished)}
        tc = ToolCall(id=f"demo_{len(done) + 1}", name=name, arguments=args)
        raw = {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"id": tc.id, "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}],
        }
        return ChatResponse(tool_calls=[tc], raw_assistant_message=raw)

    f = ("Fetch current IT tender listings",)
    d = f + ("Download a sample tender document",)
    e = d + ("Extract its text",)
    a = e + ("Analyse all tenders with isolated sub-agents",)
    n = a + ("Record the shortlist",)
    if "fetch_tender_listings" not in done:
        return call("fetch_tender_listings", "Start by finding which IT tenders are open right now.", ())
    if "download_document" not in done:
        url = observation["sample"]["document_url"]
        return call("download_document", "Pull one tender document to check the document pipeline works.", f, url=url)
    if "extract_text" not in done:
        return call("extract_text", "Convert the document to text and keep it on disk, out of context.", d, path=observation["path"])
    if "analyze_many" not in done:
        tool_msg = next(m for m in messages if m.get("name") == "fetch_tender_listings")
        ids = _parse_observation(tool_msg["content"])["tender_ids"]
        return call("analyze_many", "Score every open tender in its own clean sub-agent.", e, tender_ids=ids)
    if "write_note" not in done:
        results = observation["results"]
        ranked = sorted((r for r in results if r.get("score") is not None), key=lambda r: -r["score"])
        lines = [f"- {r['score']}/100 {r['title']}: {r['reason']}" for r in ranked[:5]]
        return call("write_note", "Record the shortlist so it stays on disk rather than in context.", a,
                    filename="shortlist.md", content="# Shortlist\n" + "\n".join(lines))
    analysis = _parse_observation(next(m for m in messages if m.get("name") == "analyze_many")["content"])
    best = max((r for r in analysis["results"] if r.get("score") is not None), key=lambda r: r["score"])
    if "generate_bid_pack" not in done:
        return call("generate_bid_pack", f"'{best['title']}' is the best fit, so prepare its bid.", n, tender_id=best["tender_id"])
    strong = [r for r in analysis["results"] if r.get("label") == "strong"]
    answer = (
        f"Analysed {len(analysis['results'])} tenders and found {len(strong)} strong fits. "
        f"Best: {best['title']} ({best['score']}/100). Its bid pack is ready to download."
    )
    return ChatResponse(content=answer, raw_assistant_message={"role": "assistant", "content": answer})


def _parse_observation(content: str) -> dict:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {}


class DemoLLM:
    model = "demo-offline"

    def __init__(self) -> None:
        self.usage = Usage()
        self._seeds = {r["external_id"]: r for r in seed_records()}

    async def _pause(self, fraction: float = 1.0) -> None:
        await asyncio.sleep(get_settings().demo_step_delay_ms / 1000 * fraction)

    async def chat(self, messages: list[dict], **kw: Any) -> str:
        await self._pause(0.5)
        return "OK (demo mode, no model was called)"

    async def chat_json(self, messages: list[dict], schema: Type[T], **kw: Any) -> T:
        await self._pause(0.5)
        user = messages[-1]["content"]
        if schema is Extraction:
            return self._extraction(user)  # type: ignore[return-value]
        if schema is FuzzyBatch:
            payload = json.loads(user)
            projects = payload["profile"]["past_projects"]
            return FuzzyBatch(verdicts=[fuzzy_verdict(i, projects) for i in payload["requirements"]])  # type: ignore[return-value]
        if schema is ChunkSummary:
            return ChunkSummary(summary=user)  # type: ignore[return-value]
        raise ValueError(f"DemoLLM cannot produce {schema.__name__}; callers must handle this")

    def _extraction(self, document: str) -> Extraction:
        m = re.search(r"Tender Reference No:\s*(SEED-\d+)", document)
        if not m or m.group(1) not in self._seeds:
            # Demo mode has no model, so an unknown document yields nothing rather than a guess.
            return Extraction(scope_summary="Demo mode can only read seed documents.", eligibility=[])
        data = dict(self._seeds[m.group(1)]["demo_extraction"])
        closing = re.search(r"Closing date and time:\s*(\d{4}-\d{2}-\d{2})", document)
        data["closing_date"] = closing.group(1) if closing else None
        return Extraction.model_validate(data)

    async def chat_tools(self, messages: list[dict], tools: list[dict], **kw: Any) -> ChatResponse:
        await self._pause()
        return _scripted_plan(messages)
