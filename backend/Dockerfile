# Build from the repo root: docker build -f backend/Dockerfile -t tenderscout-backend .
FROM python:3.11-slim

ENV UV_LINK_MODE=copy PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN pip install --no-cache-dir uv

WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock backend/
RUN uv sync --project backend --no-dev --frozen

COPY backend/ backend/
COPY data/seed/ data/seed/

# Mount a persistent disk at /data: it holds the SQLite database and the agent workspaces.
ENV DATA_DIR=/data
RUN useradd --create-home app && mkdir -p /data && chown -R app /data /app
USER app
VOLUME /data

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s CMD ["backend/.venv/bin/python", "-c", "import os,urllib.request as u; u.urlopen(f\"http://localhost:{os.environ.get('PORT','8000')}/health\", timeout=3)"]
CMD ["sh", "-c", "exec backend/.venv/bin/python -m uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
