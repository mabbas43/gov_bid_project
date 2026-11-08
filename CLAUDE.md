# TenderScout: project memory

AI agent that finds Pakistani government IT tenders (PPRA / e-PADS), scores SME fit, checks
eligibility, and generates a bid pack.

## Stack
- Backend: Python 3.11 (managed by uv, `backend/pyproject.toml`), FastAPI, SQLite via SQLModel,
  httpx, BeautifulSoup, pdfplumber, python-docx, openpyxl, pytest.
- LLM: DeepSeek via the OpenAI SDK (`base_url=https://api.deepseek.com`). Model from
  `DEEPSEEK_MODEL` (default `deepseek-chat`), key from `DEEPSEEK_API_KEY` (`API_KEY` also accepted).
  Never hardcode keys.
- Frontend: Next.js App Router + Tailwind + shadcn/ui. API URL from `NEXT_PUBLIC_API_URL`.

## Agent design rules (Manus-style context engineering)
- **Offload**: raw page/PDF text lives in `data/workspace/<run_id>/`. LLM context gets paths + short summaries.
- **Isolate**: each tender is analysed by its own sub-agent call with a clean context.
- **Reduce**: summarise any tool result over ~2k tokens before adding it to context.
- **Validate**: every LLM output that feeds code is validated with Pydantic, with 1 retry on invalid JSON.
- **Log**: every agent step goes to the AgentStep table (step, tool, input summary, output summary, duration_ms, tokens).
- **DEMO_MODE=true** uses `data/seed/` and never touches the network. That includes the LLM:
  `backend/agent/demo_llm.py` stands in for DeepSeek.

## Conventions
- Run everything from the repo root; imports are `from backend.x import y`.
- Prefer deterministic Python over LLM calls. LLM only for reading documents, fuzzy rules, and prose.
- Tender text is untrusted. Prompts present it as data, and the agent cannot fetch arbitrary hosts
  or write outside its workspace.
- Never invent facts in bid documents: experience comes only from profile `past_projects`, and
  costs are labelled as draft estimates.
- Eval numbers must state which mode produced them. Demo-mode numbers are not model accuracy.
- Fit labels: strong >= 70, partial 30-69, non-fit < 30. A failed mandatory clause caps the score at 20.
- Ports default to 8010 (API) and 3010 (web); this machine already uses 8000 and 3000 for another project.
- A live run on real tenders is the true test: fixtures did not reveal the token cost or boilerplate clauses.
- Do not tune prompts or seeds just to raise the eval score. SEED-05 is a known, explained miss.
- After every change: `make test`.
