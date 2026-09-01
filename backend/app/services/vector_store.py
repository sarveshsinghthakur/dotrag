import uuid
import json
from typing import Optional
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct,
    Filter, FieldCondition, MatchValue
)
from app.config import settings
from app.services.mistral import get_mistral_service


class VectorStore:
    """Qdrant vector store service."""

    COLLECTION_NAME = "dotrag_chunks"

    def __init__(self):
        self.client: Optional[QdrantClient] = None
        self._ensure_collection()

    def _get_client(self) -> QdrantClient:
        if self.client is None:
            self.client = QdrantClient(
                url=settings.QDRANT_URL,
                api_key=settings.QDRANT_API_KEY or None,
            )
        return self.client

    def _ensure_collection(self):
        client = self._get_client()
        collections = client.get_collections().collections
        collection_names = [c.name for c in collections]
        if self.COLLECTION_NAME not in collection_names:
            client.create_collection(
                collection_name=self.COLLECTION_NAME,
                vectors_config=VectorParams(size=4096, distance=Distance.COSINE),
            )

    async def add_chunks(
        self, chunk_ids: list[str], texts: list[str], metadatas: list[dict]
    ) -> list[str]:
        mistral = get_mistral_service()
        embeddings = await mistral.get_embeddings(texts, input_type="passage")

        client = self._get_client()
        points = []
        for i, (chunk_id, embedding, metadata) in enumerate(
            zip(chunk_ids, embeddings, metadatas)
        ):
            # Convert metadata values to strings for Qdrant
            payload = {}
            for k, v in metadata.items():
                if isinstance(v, (str, int, float, bool)):
                    payload[k] = v
                else:
                    payload[k] = json.dumps(v, default=str)
            points.append(
                PointStruct(
                    id=str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id)),
                    vector=embedding,
                    payload={"chunk_id": chunk_id, **payload},
                )
            )

        # Batch insert
        batch_size = 100
        for i in range(0, len(points), batch_size):
            client.upsert(
                collection_name=self.COLLECTION_NAME,
                points=points[i : i + batch_size],
            )

        return chunk_ids

    async def search(
        self,
        query: str,
        top_k: int = 8,
        document_id: Optional[str] = None,
        score_threshold: float = 0.3,
    ) -> list[dict]:
        mistral = get_mistral_service()
        query_embedding = (await mistral.get_embeddings([query], input_type="query"))[0]

        client = self._get_client()

        search_filter = None
        if document_id:
            search_filter = Filter(
                must=[
                    FieldCondition(key="document_id", match=MatchValue(value=document_id))
                ]
            )

        results = client.search(
            collection_name=self.COLLECTION_NAME,
            query_vector=query_embedding,
            limit=top_k,
            query_filter=search_filter,
            score_threshold=score_threshold,
        )

        search_results = []
        for hit in results:
            payload = hit.payload or {}
            search_results.append(
                {
                    "chunk_id": payload.get("chunk_id", ""),
                    "document_id": payload.get("document_id", ""),
                    "document_name": payload.get("filename", payload.get("document_name", "")),
                    "page_number": payload.get("page_number", 0),
                    "content": payload.get("content", ""),
                    "score": hit.score,
                    "metadata": {
                        k: v
                        for k, v in payload.items()
                        if k not in ("chunk_id", "document_id", "filename", "page_number", "content")
                    },
                }
            )
        return search_results

    def delete_by_document(self, document_id: str):
        client = self._get_client()
        client.delete(
            collection_name=self.COLLECTION_NAME,
            points_selector=Filter(
                must=[
                    FieldCondition(key="document_id", match=MatchValue(value=document_id))
                ]
            ),
        )

    async def close(self):
        if self.client:
            self.client.close()


_vector_store_instance: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    global _vector_store_instance
    if _vector_store_instance is None:
        _vector_store_instance = VectorStore()
    return _vector_store_instance
