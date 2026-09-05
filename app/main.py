import hmac
import os
import re
import time
from contextlib import asynccontextmanager
from uuid import uuid4
from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator
from pydantic_ai.exceptions import ModelHTTPError
from app.answering import (
    ProviderConfigurationError,
    RAGAnswer,
    answer_question,
)
from app.chunking import Chunk, load_chunks
from app.observability import get_logger
from app.vector_store import (
    close_client,
    get_index_status,
    index_documents,
    semantic_search,
)

REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,128}$")

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    close_client()

app = FastAPI(
    title="Support Knowledge Copilot",
    version="1.0.0",
    lifespan=lifespan,
)

logger = get_logger("app.requests")

@app.middleware("http")
async def log_request(request: Request, call_next):
    supplied_request_id = request.headers.get("X-Request-ID", "")
    request_id = (
        supplied_request_id
        if REQUEST_ID_PATTERN.fullmatch(supplied_request_id)
        else str(uuid4())
    )
    started_at = time.perf_counter()

    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "request_failed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "duration_ms": round(
                    (time.perf_counter() - started_at) * 1000,
                    2,
                ),
            },
        )
        raise

    logger.info(
        "request_completed",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": round(
                (time.perf_counter() - started_at) * 1000,
                2,
            ),
        },
    )

    response.headers["X-Request-ID"] = request_id
    return response

def verify_internal_api_key(
    x_internal_api_key: str | None = Header(default=None),
) -> None:
    expected_secret = os.getenv("API_SHARED_SECRET")

    if expected_secret and not hmac.compare_digest(
        x_internal_api_key or "",
        expected_secret,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal API key.",
        )

class SearchRequest(BaseModel):
    query: str = Field(
        max_length=1000,
        description="User question",
    )

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 3:
            raise ValueError("Query must contain at least 3 non-space characters.")
        return normalized

class SearchMatch(BaseModel):
    source: str
    text: str
    score: float

class SearchResponse(BaseModel):
    query: str
    matches: list[SearchMatch]

class IndexResponse(BaseModel):
    indexed_chunks: int

class IndexStatus(BaseModel):
    ready: bool
    indexed_chunks: int

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

@app.get("/ready", response_model=IndexStatus)
def ready() -> IndexStatus:
    try:
        index_status = get_index_status()
    except Exception as error:
        logger.exception("vector_store_unavailable")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "ready": False,
                "indexed_chunks": 0,
                "reason": "Vector store is unavailable.",
            },
        ) from error

    if not index_status["ready"]:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=index_status,
        )

    return IndexStatus(**index_status)

@app.get(
    "/chunks",
    response_model=list[Chunk],
    dependencies=[Depends(verify_internal_api_key)],
)
def get_chunks() -> list[Chunk]:
    return load_chunks()

@app.post(
    "/index",
    response_model=IndexResponse,
    dependencies=[Depends(verify_internal_api_key)],
)
def index() -> IndexResponse:
    return IndexResponse(indexed_chunks=index_documents())

@app.post(
    "/search",
    response_model=SearchResponse,
    dependencies=[Depends(verify_internal_api_key)],
)
def search(request: SearchRequest) -> SearchResponse:
    try:
        matches = semantic_search(request.query)
    except RuntimeError as error:
        raise HTTPException(
            status_code=409,
            detail=str(error),
        ) from error

    return SearchResponse(query=request.query, matches=matches)

@app.post(
    "/ask",
    response_model=RAGAnswer,
    dependencies=[Depends(verify_internal_api_key)],
)
def ask(request: SearchRequest) -> RAGAnswer:
    try:
        matches = semantic_search(request.query)
        return answer_question(request.query, matches)
    except ModelHTTPError as error:
        logger.warning(
            "llm_provider_error",
            extra={
                "provider_status_code": error.status_code,
            },
        )
        raise HTTPException(
            status_code=502,
            detail="LLM provider failed to process the request. Try again later.",
        ) from error
    except ProviderConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM provider is not configured.",
        ) from error
    except RuntimeError as error:
        raise HTTPException(
            status_code=409,
            detail=str(error),
        ) from error