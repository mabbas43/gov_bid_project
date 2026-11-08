import os

from backend import config, eval as ev


def test_offline_eval_prints_metrics_and_labels_its_mode(capsys, monkeypatch):
    monkeypatch.setenv("DEMO", "1")
    saved = {k: os.environ.get(k) for k in ("DATA_DIR", "DATABASE_URL")}
    from backend import db

    db.reset_engine()
    assert ev.main() == 0
    out = capsys.readouterr().out
    db.reset_engine()
    config.get_settings.cache_clear()
    for k, v in saved.items():
        monkeypatch.setenv(k, v)
    assert "OFFLINE DEMO PIPELINE" in out and "12/12 = 100%" in out
    for label in ("Avg latency per tender", "Total tokens", "Estimated DeepSeek cost"):
        assert label in out
