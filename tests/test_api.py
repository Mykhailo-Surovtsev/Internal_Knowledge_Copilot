from fastapi.testclient import TestClient
from app import main
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
def test_ready_returns_503_without_index(monkeypatch):
    monkeypatch.setattr(
        main,
        "get_index_status",
        lambda: {
            "ready": False,
            "indexed_chunks": 0,
        },
    )

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json()["detail"]["ready"] is False


def test_ready_returns_200_with_index(monkeypatch):
    monkeypatch.setattr(
        main,
        "get_index_status",
        lambda: {
            "ready": True,
            "indexed_chunks": 4,
        },
    )

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {
        "ready": True,
        "indexed_chunks": 4,
    }