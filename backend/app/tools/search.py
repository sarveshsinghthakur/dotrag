from typing import Optional
from app.services.database import get_db
from app.retrieval.retriever import get_retriever


def search_documents(query: str, document_id: Optional[str] = None, top_k: int = 8) -> dict:
    """Search across documents or within a specific document."""
    import asyncio

    retriever = get_retriever(top_k=top_k)
    doc_ids = [document_id] if document_id else None
    results = asyncio.get_event_loop().run_until_complete(
        retriever.search(query, document_ids=doc_ids)
    )
    return {
        "results": [
            {
                "document_name": r.document_name,
                "page_number": r.page_number,
                "content": r.content,
                "score": r.score,
                "chunk_id": r.chunk_id,
                "document_id": r.document_id,
            }
            for r in results
        ],
        "total": len(results),
    }


def summarize_document(document_id: str) -> dict:
    """Get document content for summarization."""
    db = get_db()
    doc = db.get_document(document_id)
    if not doc:
        return {"error": "Document not found"}

    chunks = db.get_chunks_by_document(document_id)
    full_text = "\n\n".join(c.content for c in chunks[:50])  # Limit for context

    return {
        "document_id": document_id,
        "filename": doc.filename,
        "page_count": doc.page_count,
        "content": full_text[:8000],  # Limit for context window
    }


def compare_documents(document_ids: list[str], topic: Optional[str] = None) -> dict:
    """Gather content from multiple documents for comparison."""
    db = get_db()
    docs_content = []

    for doc_id in document_ids:
        doc = db.get_document(doc_id)
        if not doc:
            continue
        chunks = db.get_chunks_by_document(doc_id)
        content = "\n\n".join(c.content for c in chunks[:30])
        docs_content.append(
            {
                "document_id": doc_id,
                "filename": doc.filename,
                "page_count": doc.page_count,
                "content": content[:4000],
            }
        )

    return {"documents": docs_content, "topic": topic}


def get_source_info(chunk_id: str) -> dict:
    """Get source information for a specific chunk."""
    db = get_db()
    chunk = db.get_chunk(chunk_id)
    if not chunk:
        return {"error": "Chunk not found"}

    doc = db.get_document(chunk.document_id)
    return {
        "chunk_id": chunk_id,
        "document_id": chunk.document_id,
        "filename": doc.filename if doc else "Unknown",
        "page_number": chunk.page_number,
        "text": chunk.content[:500],
    }


# LangChain-compatible tool definitions
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_documents",
            "description": "Search across uploaded PDF documents for relevant information. Returns matching passages with page numbers and source citations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query to find relevant content in documents",
                    },
                    "document_id": {
                        "type": "string",
                        "description": "Optional: specific document ID to search within. If omitted, searches all documents.",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of results to return (default: 8)",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "summarize_document",
            "description": "Get document content for summarization. Use this when the user asks to summarize or get an overview of a specific document.",
            "parameters": {
                "type": "object",
                "properties": {
                    "document_id": {
                        "type": "string",
                        "description": "The document ID to summarize",
                    }
                },
                "required": ["document_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_documents",
            "description": "Compare multiple documents on a specific topic or aspect.",
            "parameters": {
                "type": "object",
                "properties": {
                    "document_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of document IDs to compare",
                    },
                    "topic": {
                        "type": "string",
                        "description": "Specific topic or aspect to compare",
                    },
                },
                "required": ["document_ids"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_source_info",
            "description": "Get detailed source information for a specific text chunk, including filename, page number, and surrounding text.",
            "parameters": {
                "type": "object",
                "properties": {
                    "chunk_id": {
                        "type": "string",
                        "description": "The chunk ID to get source information for",
                    }
                },
                "required": ["chunk_id"],
            },
        },
    },
]
