from functools import lru_cache
from pathlib import Path

from qdrant_client import QdrantClient, models

from app.chunking import Chunk, load_chunks

COLLECTION_NAME = "knowledge_chunks"
EMBEDDING_MODEL = "BAAI/bge-small-en"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
QDRANT_STORAGE = PROJECT_ROOT / "storage" / "qdrant"


@lru_cache
def get_client() -> QdrantClient:
    return QdrantClient(path=str(QDRANT_STORAGE))


def index_documents() -> int:
    client = get_client()
    chunks = load_chunks()

    if client.collection_exists(COLLECTION_NAME):
        client.delete_collection(COLLECTION_NAME)

    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=models.VectorParams(
            size=client.get_embedding_size(EMBEDDING_MODEL),
            distance=models.Distance.COSINE,
        ),
    )

    client.upload_collection(
        collection_name=COLLECTION_NAME,
        vectors=[
            models.Document(text=chunk.text, model=EMBEDDING_MODEL)
            for chunk in chunks
        ],
        payload=[
            {
                "chunk_id": chunk.id,
                "source": chunk.source,
                "text": chunk.text,
            }
            for chunk in chunks
        ],
        ids=list(range(len(chunks))),
    )

    return len(chunks)


def semantic_search(query: str, limit: int = 3) -> list[dict]:
    client = get_client()

    if not client.collection_exists(COLLECTION_NAME):
        raise RuntimeError("Index is empty. Call POST /index first.")

    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=models.Document(text=query, model=EMBEDDING_MODEL),
        limit=limit,
        with_payload=True,
    ).points

    return [
        {
            "source": point.payload["source"],
            "text": point.payload["text"],
            "score": round(point.score, 3),
        }
        for point in results
    ]
def get_index_status() -> dict[str, bool | int]:
    client = get_client()

    if not client.collection_exists(COLLECTION_NAME):
        return {
            "ready": False,
            "indexed_chunks": 0,
        }

    collection = client.get_collection(COLLECTION_NAME)
    indexed_chunks = collection.points_count or 0

    return {
        "ready": indexed_chunks > 0,
        "indexed_chunks": indexed_chunks,
    }
def close_client() -> None:
    if get_client.cache_info().currsize == 0:
        return

    client = get_client()
    client.close()
    get_client.cache_clear()