"""Every test gets a throwaway database and data dir, and no real API key."""
import pytest

from backend import config, db


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("DEMO_STEP_DELAY_MS", "0")
    config.get_settings.cache_clear()
    db.reset_engine()
    db.init_db()
    yield
    db.reset_engine()
    config.get_settings.cache_clear()
