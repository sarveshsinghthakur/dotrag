import os
import uuid
from pathlib import Path
from datetime import datetime
from typing import Optional
from app.models import Document, DocumentChunk, DocumentStatus
from app.config import settings
from app.services.database import get_db
from app.services.vector_store import get_vector_store
from .pdf_loader import PDFLoader
from .chunker import DocumentChunker


class IngestionPipeline:
    """Full PDF ingestion pipeline: upload -> extract -> chunk -> embed -> store."""

    async def ingest_pdf(self, file_path: str, filename: str) -> Document:
        db = get_db()

        doc = Document(
            filename=filename,
            file_path=file_path,
            file_size=os.path.getsize(file_path),
            status=DocumentStatus.PROCESSING,
        )
        doc = db.create_document(doc)

        try:
            # Extract text from PDF
            loader = PDFLoader()
            pages = await loader.extract_pages(file_path)
            doc.page_count = len(pages)
            doc = db.update_document(doc.id, status=DocumentStatus.INDEXING)

            # Chunk the document
            chunker = DocumentChunker(
                chunk_size=settings.CHUNK_SIZE,
                chunk_overlap=settings.CHUNK_OVERLAP,
            )
            chunks = chunker.chunk_pages(pages, doc.id, filename)

            # Store chunks in database
            db.bulk_create_chunks(chunks)

            # Generate embeddings and store in vector DB
            vector_store = get_vector_store()
            chunk_ids = [c.id for c in chunks]
            texts = [c.content for c in chunks]
            metadatas = [
                {
                    "document_id": c.document_id,
                    "filename": filename,
                    "page_number": c.page_number,
                    "chunk_index": c.chunk_index,
                    "content": c.content,
                    "chunk_id": c.id,
                }
                for c in chunks
            ]

            await vector_store.add_chunks(chunk_ids, texts, metadatas)

            # Mark as ready
            doc = db.update_document(
                doc.id,
                status=DocumentStatus.READY,
                metadata={"chunk_count": len(chunks)},
            )
            return doc

        except Exception as e:
            doc = db.update_document(
                doc.id,
                status=DocumentStatus.ERROR,
                error_message=str(e),
            )
            raise

    async def delete_document(self, document_id: str) -> bool:
        db = get_db()
        doc = db.get_document(document_id)
        if not doc:
            return False

        # Delete from vector store
        try:
            vector_store = get_vector_store()
            vector_store.delete_by_document(document_id)
        except Exception:
            pass

        # Delete file
        if os.path.exists(doc.file_path):
            os.remove(doc.file_path)

        # Delete from database
        return db.delete_document(document_id)


def get_ingestion_pipeline() -> IngestionPipeline:
    return IngestionPipeline()
