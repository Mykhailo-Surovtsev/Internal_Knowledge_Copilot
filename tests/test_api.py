from fastapi.testclient import TestClient
from app import main
from app.main import app
from pydantic_ai.exceptions import ModelHTTPError

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
def test_ask_returns_502_when_llm_provider_fails(monkeypatch):
    monkeypatch.setattr(
        main,
        "semantic_search",
        lambda query: [
            {
                "source": "remote_work.md",
                "text": "Core hours are 11:00 to 16:00 Kyiv time.",
                "score": 0.9,
            }
        ],
    )

    def raise_provider_error(question, matches):
        raise ModelHTTPError(
            status_code=503,
            model_name="test-model",
            body={},
        )

    monkeypatch.setattr(
        main,
        "answer_question",
        raise_provider_error,
    )

    response = client.post(
        "/ask",
        json={
            "query": "What are the core hours?",
        },
    )

    assert response.status_code == 502
    assert response.json()["detail"] == (
        "LLM provider failed to process the request. Try again later."
    )