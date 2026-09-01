from typing import Optional
from app.models import SearchResult
from app.services.vector_store import get_vector_store
from app.services.database import get_db


class Retriever:
    """Document retrieval with semantic search and metadata filtering."""

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
        vector_store = get_vector_store()

        effective_top_k = top_k or self.top_k
        # Search each document separately if filtering
        all_results = []

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

        # Filter by page numbers if specified
        if page_numbers:
            all_results = [
                r for r in all_results if r["page_number"] in page_numbers
            ]

        # Sort by score and take top_k
        all_results.sort(key=lambda x: x["score"], reverse=True)
        all_results = all_results[:effective_top_k]

        # Convert to SearchResult models
        search_results = []
        for r in all_results:
            search_results.append(
                SearchResult(
                    chunk_id=r.get("chunk_id", ""),
                    document_id=r.get("document_id", ""),
                    document_name=r.get("document_name", ""),
                    page_number=r.get("page_number", 0),
                    content=r.get("content", ""),
                    score=r.get("score", 0.0),
                    metadata=r.get("metadata", {}),
                )
            )

        return search_results

    def build_context(self, results: list[SearchResult], max_tokens: int = 6000) -> str:
        """Build context string from search results for LLM."""
        context_parts = []
        current_length = 0

        for i, result in enumerate(results):
            header = f"[Source {i + 1}: {result.document_name}, Page {result.page_number}]"
            content = result.content
            entry = f"{header}\n{content}\n"

            if current_length + len(entry) > max_tokens * 4:  # Rough char estimate
                break

            context_parts.append(entry)
            current_length += len(entry)

        return "\n---\n".join(context_parts)


def get_retriever(top_k: int = 8) -> Retriever:
    return Retriever(top_k=top_k)
