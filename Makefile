.PHONY: install dev backend frontend test seed eval

PY := uv run --project backend python
API_PORT ?= 8010
WEB_PORT ?= 3010

install:
	uv sync --project backend
	cd frontend && npm install

backend:
	CORS_ORIGINS=http://localhost:$(WEB_PORT),http://127.0.0.1:$(WEB_PORT) $(PY) -m uvicorn backend.main:app --reload --reload-dir backend --port $(API_PORT)

frontend:
	cd frontend && NEXT_PUBLIC_API_URL=http://localhost:$(API_PORT) npx next dev --port $(WEB_PORT)

dev:
	@$(MAKE) -j2 backend frontend

test:
	$(PY) -m pytest -c backend/pyproject.toml --rootdir=. backend/tests -q
	cd frontend && npx tsc --noEmit

seed:
	$(PY) -m backend.seed

eval:
	$(PY) -m backend.eval
