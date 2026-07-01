"""Smoke tests — FastAPI app boot + DB-backed dependency injection."""

from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_ok() -> None:
    response = TestClient(app).get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_db_uses_session_dependency(client: TestClient) -> None:
    """Hello-world DB route — proves the session dependency is wired up."""
    response = client.get("/api/health/db")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert isinstance(body["stock_count"], int)
