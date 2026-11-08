from fastapi.testclient import TestClient

from backend.main import app


def test_health():
    with TestClient(app) as c:
        assert c.get("/health").json() == {"status": "ok"}
