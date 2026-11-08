"""Engine and session helpers. Sessions are short-lived so background runs and SSE can share SQLite."""
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine

from backend.config import get_settings

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(
            settings.db_url, connect_args={"check_same_thread": False, "timeout": 30}
        )

        @event.listens_for(_engine, "connect")
        def _pragmas(conn, _record):  # WAL lets the SSE reader run alongside the agent writer.
            cur = conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()

    return _engine


def reset_engine() -> None:
    """Drop the cached engine (tests point DATABASE_URL at a temp file)."""
    global _engine
    if _engine is not None:
        _engine.dispose()
    _engine = None


def init_db() -> None:
    import backend.models  # noqa: F401  (registers tables)

    SQLModel.metadata.create_all(get_engine())


@contextmanager
def session_scope() -> Iterator[Session]:
    with Session(get_engine(), expire_on_commit=False) as session:
        yield session


def get_session() -> Iterator[Session]:
    with Session(get_engine(), expire_on_commit=False) as session:
        yield session
