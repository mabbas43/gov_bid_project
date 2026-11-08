from fastapi.testclient import TestClient
from sqlmodel import select

from backend import config
from backend.agent.orchestrator import run_agent
from backend.db import session_scope
from backend.llm import DeepSeekLLM
from backend.main import app
from backend.models import AgentRun, Tender
from backend.seed import upsert_seed_tenders


def test_demo_toggle_persists_and_controls_new_runs():
    with TestClient(app) as c:
        assert c.put("/settings", json={"demo_mode": False}).json() == {"demo_mode": False}
        assert c.get("/settings").json() == {"demo_mode": False}
        assert c.get("/dashboard").json()["demo_mode"] is False
        assert c.put("/settings", json={"demo_mode": True}).json() == {"demo_mode": True}
    from backend.settings_service import get_demo_mode

    with session_scope() as s:
        assert get_demo_mode(s) is True


def test_demo_mode_hides_live_tenders():
    with TestClient(app) as c:
        with session_scope() as s:
            upsert_seed_tenders(s)
            s.add(Tender(external_id="TS1", title="Live one", source="ppra"))
            s.commit()
        c.put("/settings", json={"demo_mode": True})
        assert all(t["source"] == "seed" for t in c.get("/tenders").json())
        c.put("/settings", json={"demo_mode": False})
        live = c.get("/tenders").json()
        assert [t["source"] for t in live] == ["ppra"]  # sample tenders must not pass as real
        assert c.get("/dashboard").json()["tenders_total"] == 1


def test_live_mode_shows_seeds_only_when_there_are_no_real_tenders():
    with TestClient(app) as c:
        c.put("/settings", json={"demo_mode": False})
        assert {t["source"] for t in c.get("/tenders").json()} == {"seed"}


async def test_missing_key_in_live_mode_fails_cleanly(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    monkeypatch.setenv("API_KEY", "")
    config.get_settings.cache_clear()
    with session_scope() as s:
        run = AgentRun(goal="x", demo_mode=False)
        s.add(run)
        s.commit()
        run_id = run.id
    await run_agent(run_id)
    with session_scope() as s:
        run = s.get(AgentRun, run_id)
    assert run.status == "failed" and "DEEPSEEK_API_KEY" in run.error and "Demo mode" in run.error


def test_llm_ping_without_key_is_a_clean_502(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    monkeypatch.setenv("API_KEY", "")
    config.get_settings.cache_clear()
    with TestClient(app) as c:
        r = c.get("/llm-ping")
    assert r.status_code == 502 and "DEEPSEEK_API_KEY" in r.json()["detail"]


def test_cors_allows_configured_origin_only():
    with TestClient(app) as c:
        ok = c.options("/health", headers={"Origin": "http://localhost:3010", "Access-Control-Request-Method": "GET"})
        bad = c.options("/health", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:3010"
    assert "access-control-allow-origin" not in bad.headers


def test_interrupted_runs_are_marked_failed_on_startup():
    with session_scope() as s:
        run = AgentRun(goal="x", status="running")
        s.add(run)
        s.commit()
        run_id = run.id
    with TestClient(app):
        pass
    with session_scope() as s:
        run = s.get(AgentRun, run_id)
    assert run.status == "failed" and "restarted" in run.error


def test_fresh_install_has_tenders():
    with TestClient(app) as c:
        assert len(c.get("/tenders").json()) == 12


def test_key_alias_from_env_file_name(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("API_KEY", "from-alias")
    config.get_settings.cache_clear()
    assert config.get_settings().deepseek_api_key == "from-alias"
    assert DeepSeekLLM().model == "deepseek-chat"
