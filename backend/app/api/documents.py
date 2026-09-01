import os
import uuid
import shutil
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from app.config import settings
from app.models import Document, DocumentStatus, UploadResponse, DocumentInfo
from app.services.database import get_db
from app.ingestion.pipeline import get_ingestion_pipeline

router = APIRouter(prefix="/api/documents", tags=["documents"])


async def process_document_background(file_path: str, filename: str):
    """Background task to process uploaded PDF."""
    pipeline = get_ingestion_pipeline()
    try:
        await pipeline.ingest_pdf(file_path, filename)
    except Exception as e:
        db = get_db()
        docs = db.list_documents()
        for doc in docs:
            if doc.file_path == file_path:
                db.update_document(doc.id, status=DocumentStatus.ERROR, error_message=str(e))
                break


@router.post("/upload", response_model=UploadResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    # Validate file type
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    # Validate file size
    content = await file.read()
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"File size exceeds maximum of {settings.MAX_UPLOAD_SIZE_MB}MB",
        )

    # Save file
    file_id = str(uuid.uuid4())
    file_path = settings.UPLOAD_DIR / f"{file_id}_{file.filename}"
    with open(file_path, "wb") as f:
        f.write(content)

    # Create document record
    db = get_db()
    doc = Document(
        filename=file.filename,
        file_path=str(file_path),
        file_size=len(content),
        status=DocumentStatus.UPLOADING,
    )
    doc = db.create_document(doc)

    # Process in background
    background_tasks.add_task(process_document_background, str(file_path), file.filename)

    return UploadResponse(document=doc, message="PDF uploaded successfully. Processing has started.")


@router.get("/", response_model=list[DocumentInfo])
async def list_documents():
    db = get_db()
    docs = db.list_documents()
    return [
        DocumentInfo(
            id=doc.id,
            filename=doc.filename,
            page_count=doc.page_count,
            file_size=doc.file_size,
            status=doc.status,
            created_at=doc.created_at,
            chunk_count=doc.metadata.get("chunk_count", 0),
        )
        for doc in docs
    ]


@router.get("/{document_id}", response_model=DocumentInfo)
async def get_document(document_id: str):
    db = get_db()
    doc = db.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentInfo(
        id=doc.id,
        filename=doc.filename,
        page_count=doc.page_count,
        file_size=doc.file_size,
        status=doc.status,
        created_at=doc.created_at,
        chunk_count=doc.metadata.get("chunk_count", 0),
    )


@router.get("/{document_id}/file")
async def download_document_file(document_id: str):
    db = get_db()
    doc = db.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    file_path = Path(doc.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="PDF file not found on disk")
    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        filename=doc.filename,
    )


@router.delete("/{document_id}")
async def delete_document(document_id: str):
    pipeline = get_ingestion_pipeline()
    success = await pipeline.delete_document(document_id)
    if not success:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"message": "Document deleted successfully"}


@router.get("/{document_id}/pages/{page_number}")
async def get_document_page(document_id: str, page_number: int):
    db = get_db()
    doc = db.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    chunks = db.get_chunks_by_document(document_id)
    page_chunks = [c for c in chunks if c.page_number == page_number]

    return {
        "document_id": document_id,
        "page_number": page_number,
        "content": "\n\n".join(c.content for c in page_chunks),
        "chunk_count": len(page_chunks),
    }
