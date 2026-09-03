from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.chunking import Chunk, load_chunks
from app.vector_store import index_documents, semantic_search
from app.answering import RAGAnswer, answer_question

app = FastAPI(
    title="Internal Knowledge Copilot",
    version="0.2.0",
)


class SearchRequest(BaseModel):
    query: str = Field(min_length=3, description="User question")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/chunks")
def get_chunks() -> list[Chunk]:
    return load_chunks()


@app.post("/index")
def index() -> dict:
    indexed_chunks = index_documents()
    return {"indexed_chunks": indexed_chunks}


@app.post("/search")
def search(request: SearchRequest) -> dict:
    try:
        matches = semantic_search(request.query)
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error

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
        raise HTTPException(status_code=409, detail=str(error)) from error