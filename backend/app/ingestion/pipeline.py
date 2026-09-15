import os
from pathlib import Path
from app.models import Document, DocumentChunk, DocumentStatus, DocumentScope
from app.config import settings
from app.services.database import get_db
from app.services.vector_store import get_vector_store
from .pdf_loader import FileLoader, SUPPORTED_IMAGE_TYPES
from .chunker import DocumentChunker


class IngestionPipeline:
    """Full file ingestion pipeline: upload → extract → chunk → embed → store.

    Supports PDF and image files.  The document record is created by the API
    endpoint (documents.py) BEFORE calling this pipeline.  This pipeline only
    updates the existing record — it does NOT create duplicates.

    If Qdrant is unavailable, documents are still marked READY and the DB
    chunks are used as a fallback for retrieval.
    """

    async def ingest_file(
        self,
        file_path: str,
        filename: str,
        document_id: str,
        scope: str = "library",
        conversation_id: str | None = None,
    ) -> Document:
        db = get_db()

        doc = db.update_document(document_id, status=DocumentStatus.PROCESSING)
        if not doc:
            raise ValueError(f"Document {document_id} not found in database")

        try:
            # ── 1. Extract text ──────────────────────────────────────────────
            loader = FileLoader()
            pages = await loader.extract_pages(file_path)

            if not pages:
                raise ValueError(
                    "No readable content could be extracted from this file. "
                    "The PDF may be encrypted or contain only scanned images without OCR support."
                )

            doc = db.update_document(
                document_id,
                page_count=len(pages),
                status=DocumentStatus.INDEXING,
            )

            # ── 2. Chunk ─────────────────────────────────────────────────────
            chunker = DocumentChunker(
                chunk_size=settings.CHUNK_SIZE,
                chunk_overlap=settings.CHUNK_OVERLAP,
            )
            chunks = chunker.chunk_pages(pages, document_id, filename)
            db.bulk_create_chunks(chunks)

            # ── 3. Vector index (optional — Qdrant may not be running) ───────
            vector_indexed = False
            try:
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
                        "scope": scope,
                        "conversation_id": conversation_id or "",
                    }
                    for c in chunks
                ]
                await vector_store.add_chunks(chunk_ids, texts, metadatas)
                vector_indexed = True
            except Exception as vec_err:
                # Qdrant is unavailable — document is still usable via DB fallback
                print(f"[WARN] Vector store unavailable, using DB-only retrieval: {vec_err}")

            # ── 4. Mark ready ─────────────────────────────────────────────────
            doc = db.update_document(
                document_id,
                status=DocumentStatus.READY,
                page_count=len(pages),
                metadata={
                    "chunk_count": len(chunks),
                    "vector_indexed": vector_indexed,
                },
            )
            return doc

        except Exception as e:
            db.update_document(
                document_id,
                status=DocumentStatus.ERROR,
                error_message=str(e),
            )
            raise

    # Backward-compat alias
    async def ingest_pdf(self, file_path: str, filename: str, document_id: str) -> Document:
        return await self.ingest_file(file_path, filename, document_id)

    async def delete_document(self, document_id: str) -> bool:
        db = get_db()
        doc = db.get_document(document_id)
        if not doc:
            return False

        try:
            vector_store = get_vector_store()
            vector_store.delete_by_document(document_id)
        except Exception:
            pass

        if os.path.exists(doc.file_path):
            os.remove(doc.file_path)

        return db.delete_document(document_id)


def get_ingestion_pipeline() -> IngestionPipeline:
    return IngestionPipeline()
