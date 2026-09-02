from fastapi import FastAPI
from pydantic import BaseModel, Field
from app.chunking import Chunk, load_chunks

app = FastAPI(
    title="Internal Knowledge Copilot",
    version="0.1.0",
)


class SearchRequest(BaseModel):
    query: str = Field(min_length=3, description="User question")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/search")
def search(request: SearchRequest) -> dict:
    return {
        "query": request.query,
        "matches": [],
        "message": "RAG retrieval will be implemented next.",
    }
@app.get("/chunks")
def get_chunks() -> list[Chunk]:
    return load_chunks()