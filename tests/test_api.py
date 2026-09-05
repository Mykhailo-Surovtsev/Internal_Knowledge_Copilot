from fastapi.testclient import TestClient
import pytest
from app import main
from app.answering import NO_ANSWER_MESSAGE, ProviderConfigurationError
from app.main import app
from pydantic_ai.exceptions import ModelHTTPError

client = TestClient(app)

@pytest.fixture(autouse=True)
def disable_optional_internal_key(monkeypatch):
    monkeypatch.delenv("API_SHARED_SECRET", raising=False)

def test_health_endpoint() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_search_rejects_short_query() -> None:
    response = client.post("/search", json={"query": "hi"})

    assert response.status_code == 422

def test_search_rejects_blank_query() -> None:
    response = client.post("/search", json={"query": "   "})

    assert response.status_code == 422


def test_search_requires_internal_key_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("API_SHARED_SECRET", "test-secret")

    denied = client.post("/search", json={"query": "What are core hours?"})

    assert denied.status_code == 401

    monkeypatch.setattr(main, "semantic_search", lambda query: [])
    allowed = client.post(
        "/search",
        headers={"X-Internal-Api-Key": "test-secret"},
        json={"query": "What are core hours?"},
    )

    assert allowed.status_code == 200
    assert allowed.json()["matches"] == []
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

def test_ask_returns_safe_fallback_without_context(monkeypatch) -> None:
    monkeypatch.setattr(main, "semantic_search", lambda query: [])

    response = client.post(
        "/ask",
        json={"query": "What is the parental leave policy?"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "answer": NO_ANSWER_MESSAGE,
        "sources": [],
        "grounded": False,
    }

def test_ask_returns_503_when_llm_provider_is_not_configured(monkeypatch) -> None:
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

    def raise_configuration_error(question, matches):
        raise ProviderConfigurationError("GROQ_API_KEY is not configured.")

    monkeypatch.setattr(main, "answer_question", raise_configuration_error)

    response = client.post(
        "/ask",
        json={"query": "What are the core hours?"},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "LLM provider is not configured."

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