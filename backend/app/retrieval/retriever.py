from typing import Optional
from app.models import SearchResult
from app.services.vector_store import get_vector_store
from app.services.database import get_db


class Retriever:
    """Document retrieval with semantic search and DB fallback.

    Primary path: Qdrant vector search (requires Qdrant running).
    Fallback path: simple keyword/full-text scan of DB chunks when Qdrant
                   is unavailable or returns no results.
    """

    def __init__(self, top_k: int = 8, score_threshold: float = 0.3):
        self.top_k = top_k
        self.score_threshold = score_threshold

    async def search(
        self,
        query: str,
        document_ids: Optional[list[str]] = None,
        page_numbers: Optional[list[int]] = None,
        top_k: Optional[int] = None,
    ) -> list[SearchResult]:
        effective_top_k = top_k or self.top_k

        # ── 1. Try vector search ─────────────────────────────────────────────
        vector_results: list[dict] = []
        try:
            vector_store = get_vector_store()
            all_results: list[dict] = []

            if document_ids:
                for doc_id in document_ids:
                    results = await vector_store.search(
                        query=query,
                        top_k=effective_top_k,
                        document_id=doc_id,
                        score_threshold=self.score_threshold,
                    )
                    all_results.extend(results)
            else:
                all_results = await vector_store.search(
                    query=query,
                    top_k=effective_top_k,
                    score_threshold=self.score_threshold,
                )

            if page_numbers:
                all_results = [r for r in all_results if r["page_number"] in page_numbers]

            all_results.sort(key=lambda x: x["score"], reverse=True)
            vector_results = all_results[:effective_top_k]
        except Exception:
            pass  # Qdrant down — will fall back to DB

        if vector_results:
            return self._to_models(vector_results)

        # ── 2. DB fallback: keyword scan ──────────────────────────────────────
        db_results = self._db_keyword_search(query, document_ids, page_numbers, effective_top_k)
        return self._to_models(db_results)

    def _db_keyword_search(
        self,
        query: str,
        document_ids: Optional[list[str]],
        page_numbers: Optional[list[int]],
        top_k: int,
    ) -> list[dict]:
        """Simple keyword relevance search over stored DB chunks."""
        db = get_db()
        query_terms = [t.lower().strip() for t in query.split() if len(t.strip()) > 2]

        # Gather candidate chunks
        if document_ids:
            candidates = []
            for doc_id in document_ids:
                candidates.extend(db.get_chunks_by_document(doc_id))
        else:
            # All chunks from all documents
            candidates = list(db.chunks.values())

        if page_numbers:
            candidates = [c for c in candidates if c.page_number in page_numbers]

        # Score by term frequency
        scored = []
        for chunk in candidates:
            text_lower = chunk.content.lower()
            score = sum(text_lower.count(term) for term in query_terms)
            if score > 0:
                doc = db.get_document(chunk.document_id)
                scored.append({
                    "chunk_id": chunk.id,
                    "document_id": chunk.document_id,
                    "document_name": doc.filename if doc else "",
                    "page_number": chunk.page_number,
                    "content": chunk.content,
                    "score": min(score / max(len(query_terms), 1), 1.0),
                    "metadata": chunk.metadata,
                })

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    @staticmethod
    def _to_models(raw: list[dict]) -> list[SearchResult]:
        return [
            SearchResult(
                chunk_id=r.get("chunk_id", ""),
                document_id=r.get("document_id", ""),
                document_name=r.get("document_name", ""),
                page_number=r.get("page_number", 0),
                content=r.get("content", ""),
                score=r.get("score", 0.0),
                metadata=r.get("metadata", {}),
            )
            for r in raw
        ]

    def build_context(self, results: list[SearchResult], max_tokens: int = 6000) -> str:
        """Build context string from search results for the LLM."""
        context_parts = []
        current_length = 0

        for i, result in enumerate(results):
            header = f"[Source {i + 1}: {result.document_name}, Page {result.page_number}]"
            entry = f"{header}\n{result.content}\n"

            if current_length + len(entry) > max_tokens * 4:
                break

            context_parts.append(entry)
            current_length += len(entry)

        return "\n---\n".join(context_parts)


def get_retriever(top_k: int = 8) -> Retriever:
    return Retriever(top_k=top_k)
