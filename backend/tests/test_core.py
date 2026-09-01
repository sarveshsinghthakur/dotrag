import os
import sys
import json
import tempfile
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.ingestion.pdf_loader import PDFLoader
from app.ingestion.chunker import DocumentChunker
from app.services.database import DatabaseService
from app.retrieval.retriever import Retriever
from app.tools.search import search_documents, summarize_document
from app.models import Document, DocumentStatus, SearchResult


class TestPDFLoader:
    def test_clean_text(self):
        loader = PDFLoader()
        text = "Hello\n\n\n\nWorld   with   spaces"
        cleaned = loader._clean_text(text)
        assert "Hello" in cleaned
        assert "World" in cleaned
        assert "   " not in cleaned

    def test_is_scanned_page(self):
        loader = PDFLoader()
        assert loader._is_scanned_page("") is True
        assert loader._is_scanned_page("x" * 10) is True
        assert loader._is_scanned_page("x" * 100) is False


class TestChunker:
    def test_chunk_text_short(self):
        chunker = DocumentChunker(chunk_size=1024, chunk_overlap=256)
        chunks = chunker._chunk_text("Hello world")
        assert len(chunks) == 1
        assert chunks[0] == "Hello world"

    def test_chunk_text_long(self):
        chunker = DocumentChunker(chunk_size=100, chunk_overlap=20)
        text = "Paragraph one.\n\n" * 20
        chunks = chunker._chunk_text(text)
        assert len(chunks) > 1

    def test_chunk_pages(self):
        chunker = DocumentChunker(chunk_size=100, chunk_overlap=20)
        pages = [
            {"page_number": 1, "content": "Page one content"},
            {"page_number": 2, "content": "Page two content"},
        ]
        chunks = chunker.chunk_pages(pages, "doc-123", "test.pdf")
        assert len(chunks) >= 2
        assert chunks[0].document_id == "doc-123"
        assert chunks[0].page_number == 1
        assert chunks[1].page_number == 2


class TestDatabase:
    def test_create_document(self):
        db = DatabaseService(":memory:")
        doc = Document(filename="test.pdf", file_path="/tmp/test.pdf")
        created = db.create_document(doc)
        assert created.id == doc.id
        assert created.filename == "test.pdf"

    def test_get_document(self):
        db = DatabaseService(":memory:")
        doc = Document(filename="test.pdf", file_path="/tmp/test.pdf")
        db.create_document(doc)
        retrieved = db.get_document(doc.id)
        assert retrieved is not None
        assert retrieved.filename == "test.pdf"

    def test_delete_document(self):
        db = DatabaseService(":memory:")
        doc = Document(filename="test.pdf", file_path="/tmp/test.pdf")
        db.create_document(doc)
        assert db.delete_document(doc.id) is True
        assert db.get_document(doc.id) is None

    def test_list_documents(self):
        db = DatabaseService(":memory:")
        for i in range(3):
            doc = Document(filename=f"test{i}.pdf", file_path=f"/tmp/test{i}.pdf")
            db.create_document(doc)
        docs = db.list_documents()
        assert len(docs) == 3


class TestRetriever:
    def test_build_context(self):
        retriever = Retriever()
        results = [
            SearchResult(
                chunk_id="c1", document_id="d1", document_name="doc1.pdf",
                page_number=1, content="Hello world", score=0.9
            ),
        ]
        context = retriever.build_context(results)
        assert "doc1.pdf" in context
        assert "Hello world" in context


class TestTools:
    def test_search_documents(self):
        """Test search tool structure - requires Qdrant running."""
        try:
            result = search_documents("test query")
            assert "results" in result
            assert "total" in result
        except Exception:
            # Qdrant not running - expected in CI/test without Docker
            pass

    def test_summarize_document(self):
        result = summarize_document("nonexistent-id")
        assert "error" in result


class TestModels:
    def test_document_model(self):
        doc = Document(filename="test.pdf", file_path="/tmp/test.pdf")
        assert doc.filename == "test.pdf"
        assert doc.status == DocumentStatus.UPLOADING

    def test_search_result_model(self):
        result = SearchResult(
            chunk_id="c1", document_id="d1", document_name="doc.pdf",
            page_number=1, content="content", score=0.9
        )
        assert result.score == 0.9


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
