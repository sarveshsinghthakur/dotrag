from fastapi import APIRouter
from app.models import SearchRequest, SearchResponse, SearchResult
from app.retrieval.retriever import get_retriever

router = APIRouter(prefix="/api/search", tags=["search"])


@router.post("/", response_model=SearchResponse)
async def search(request: SearchRequest):
    retriever = get_retriever(top_k=request.top_k)

    results = await retriever.search(
        query=request.query,
        document_ids=request.document_ids if request.document_ids else None,
        page_numbers=request.page_numbers if request.page_numbers else None,
        top_k=request.top_k,
    )

    return SearchResponse(
        results=results,
        query=request.query,
        total_results=len(results),
    )
