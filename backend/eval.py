"""make eval: analyses the 12 seed tenders and scores the results against the expected labels.

Uses real DeepSeek when a key is available. It runs against a throwaway database, so your dashboard is
untouched. `make eval DEMO=1` (or no key) runs the offline pipeline instead and says so, because those
numbers only test the rules, not the model.
"""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import time
from pathlib import Path


def _configure(tmp: str) -> None:
    os.environ["DATA_DIR"] = tmp
    os.environ["DATABASE_URL"] = f"sqlite:///{Path(tmp) / 'eval.db'}"
    os.environ["DEMO_STEP_DELAY_MS"] = "0"


def _table(rows: list[list[str]], headers: list[str], right: set[int]) -> str:
    widths = [max(len(str(r[i])) for r in [headers, *rows]) for i in range(len(headers))]
    def line(row: list[str]) -> str:
        return " | ".join(str(c).rjust(widths[i]) if i in right else str(c).ljust(widths[i]) for i, c in enumerate(row))
    return "\n".join([line(headers), "-+-".join("-" * w for w in widths), *(line(r) for r in rows)])


def _truncate(text: str, width: int = 46) -> str:
    return text if len(text) <= width else text[: width - 1] + "…"


async def run(demo: bool) -> int:
    from sqlmodel import select

    from backend.agent.analyst import analyze_many
    from backend.agent.llm_factory import get_llm
    from backend.config import get_settings
    from backend.db import init_db, session_scope
    from backend.llm import Usage
    from backend.models import Tender
    from backend.seed import expected_labels, main as load_seed

    init_db()
    load_seed()
    labels = expected_labels()
    with session_scope() as s:
        ids = [t.id for t in s.exec(select(Tender).order_by(Tender.external_id)).all()]

    started = time.perf_counter()
    outcomes = await analyze_many(ids, lambda: get_llm(demo))
    wall = time.perf_counter() - started

    outcomes.sort(key=lambda o: o.external_id)
    rows, correct, total_latency = [], 0, 0
    usage = Usage()
    for o in outcomes:
        expected = labels[o.external_id]
        ok = o.label == expected
        correct += ok
        total_latency += o.duration_ms
        usage.add(o.prompt_tokens, o.completion_tokens)
        rows.append([
            o.external_id, _truncate(o.title), expected, o.label or o.status,
            "-" if o.score is None else str(o.score), "yes" if ok else "NO",
            f"{o.duration_ms / 1000:.1f}", f"{o.prompt_tokens + o.completion_tokens:,}",
        ])
    print(_table(rows, ["Tender", "Title", "Expected", "Got", "Score", "OK", "Secs", "Tokens"], {4, 6, 7}))

    n = len(outcomes)
    settings = get_settings()
    per_class = []
    for cls in ("strong", "partial", "non_fit"):
        members = [o for o in outcomes if labels[o.external_id] == cls]
        per_class.append(f"{cls} {sum(o.label == cls for o in members)}/{len(members)}")
    mode = "OFFLINE DEMO PIPELINE: tests rules only, not model accuracy" if demo else f"LIVE DeepSeek ({settings.deepseek_model})"
    print()
    print(f"Mode                      {mode}")
    print(f"Fit classification        {correct}/{n} = {correct / n:.0%}  ({', '.join(per_class)})")
    print(f"Avg latency per tender    {total_latency / n / 1000:.1f} s  (wall clock {wall:.1f} s at 5 concurrent)")
    print(f"Total tokens              {usage.total_tokens:,}  ({usage.prompt_tokens:,} in, {usage.completion_tokens:,} out)")
    print(
        f"Estimated DeepSeek cost   ${usage.cost_usd():.4f}  "
        f"(at ${settings.deepseek_input_usd_per_m}/M in, ${settings.deepseek_output_usd_per_m}/M out; set by env, check current pricing)"
    )
    errors = [o for o in outcomes if o.status != "analyzed"]
    for o in errors:
        print(f"Failed: {o.external_id}: {o.status}: {o.reason}", file=sys.stderr)
    return 1 if errors else 0


def main() -> int:
    from backend.config import get_settings

    key = get_settings().deepseek_api_key
    demo = os.environ.get("DEMO") == "1" or "--demo" in sys.argv or not key
    if not key and not demo:
        print("No DEEPSEEK_API_KEY.", file=sys.stderr)
    if demo and not key:
        print("No DEEPSEEK_API_KEY found: running the offline pipeline instead.\n", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        _configure(tmp)
        get_settings.cache_clear()
        return asyncio.run(run(demo))


if __name__ == "__main__":
    sys.exit(main())
