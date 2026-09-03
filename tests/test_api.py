from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_search_rejects_short_query() -> None:
    response = client.post("/search", json={"query": "hi"})

    assert response.status_code == 422
def test_health_returns_request_id():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.headers["x-request-id"]