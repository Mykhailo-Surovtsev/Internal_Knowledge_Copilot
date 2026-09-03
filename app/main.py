import time
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from app.answering import RAGAnswer, answer_question
from app.chunking import Chunk, load_chunks
from app.observability import get_logger
from app.vector_store import (
    get_index_status,
    index_documents,
    semantic_search,
)

app = FastAPI(
    title="Internal Knowledge Copilot",
    version="0.3.0",
)

logger = get_logger("app.requests")


@app.middleware("http")
async def log_request(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid4()))
    started_at = time.perf_counter()

    response = await call_next(request)

    duration_ms = round((time.perf_counter() - started_at) * 1000, 2)

    logger.info(
        "request_completed",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        },
    )

    response.headers["X-Request-ID"] = request_id
    return response

class SearchRequest(BaseModel):
    query: str = Field(
        min_length=3,
        description="User question",
    )

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

@app.get("/ready")
def ready() -> dict:
    status = get_index_status()

    if not status["ready"]:
        raise HTTPException(
            status_code=503,
            detail=status,
        )

    return status

@app.get("/chunks", response_model=list[Chunk])
def get_chunks() -> list[Chunk]:
    return load_chunks()

@app.post("/index")
def index() -> dict[str, int]:
    indexed_chunks = index_documents()
    return {"indexed_chunks": indexed_chunks}

@app.post("/search")
def search(request: SearchRequest) -> dict:
    try:
        matches = semantic_search(request.query)
    except RuntimeError as error:
        raise HTTPException(
            status_code=409,
            detail=str(error),
        ) from error

    return {
        "query": request.query,
        "matches": matches,
    }

@app.post("/ask", response_model=RAGAnswer)
def ask(request: SearchRequest) -> RAGAnswer:
    try:
        matches = semantic_search(request.query)
        return answer_question(request.query, matches)
    except RuntimeError as error:
        raise HTTPException(
            status_code=409,
            detail=str(error),
        ) from error