import os
import uuid
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from app.config import settings
from app.models import Document, DocumentStatus, DocumentScope, UploadResponse, DocumentInfo
from app.services.database import get_db
from app.ingestion.pipeline import get_ingestion_pipeline
from app.ingestion.pdf_loader import SUPPORTED_IMAGE_TYPES

router = APIRouter(prefix="/api/documents", tags=["documents"])

# All supported MIME types
ALLOWED_EXTENSIONS = {".pdf"} | SUPPORTED_IMAGE_TYPES
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/bmp",
    "image/tiff",
    "image/webp",
}


def _detect_file_type(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        return "pdf"
    if ext in SUPPORTED_IMAGE_TYPES:
        return "image"
    return "unknown"


async def process_document_background(
    file_path: str,
    filename: str,
    document_id: str,
    scope: str,
    conversation_id: str | None,
):
    pipeline = get_ingestion_pipeline()
    try:
        await pipeline.ingest_file(file_path, filename, document_id, scope, conversation_id)
    except Exception as e:
        db = get_db()
        db.update_document(document_id, status=DocumentStatus.ERROR, error_message=str(e))


@router.post("/upload", response_model=UploadResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    scope: str = Form(default="library"),
    conversation_id: str | None = Form(default=None),
):
    # Validate extension
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: PDF and images (jpg, png, gif, bmp, tiff, webp).",
        )

    # Validate scope
    if scope not in ("library", "chat"):
        scope = "library"
    if scope == "chat" and not conversation_id:
        scope = "library"  # graceful fallback

    # Read + size check
    content = await file.read()
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"File size exceeds maximum of {settings.MAX_UPLOAD_SIZE_MB} MB",
        )

    # Save file
    file_id = str(uuid.uuid4())
    safe_filename = file.filename.replace(" ", "_")
    file_path = settings.UPLOAD_DIR / f"{file_id}_{safe_filename}"
    with open(file_path, "wb") as f:
        f.write(content)

    file_type = _detect_file_type(file.filename)

    # Normalise scope enum
    doc_scope = DocumentScope.CHAT if scope == "chat" else DocumentScope.LIBRARY

    db = get_db()
    doc = Document(
        filename=file.filename,
        file_path=str(file_path),
        file_type=file_type,
        file_size=len(content),
        status=DocumentStatus.UPLOADING,
        scope=doc_scope,
        conversation_id=conversation_id if scope == "chat" else None,
    )
    doc = db.create_document(doc)

    background_tasks.add_task(
        process_document_background,
        str(file_path),
        file.filename,
        doc.id,
        scope,
        conversation_id,
    )

    return UploadResponse(
        document=doc,
        message=f"{'PDF' if file_type == 'pdf' else 'Image'} uploaded successfully. Processing has started.",
    )


@router.get("/", response_model=list[DocumentInfo])
async def list_documents(scope: str | None = None, conversation_id: str | None = None):
    """List documents.

    - No params: returns all documents.
    - scope=library: library-only documents.
    - scope=chat&conversation_id=X: documents scoped to chat X.
    - scope=all_for_chat&conversation_id=X: library docs + chat-X docs (used by retrieval).
    """
    db = get_db()
    docs = db.list_documents()

    if scope == "library":
        docs = [d for d in docs if d.scope == DocumentScope.LIBRARY]
    elif scope == "chat" and conversation_id:
        docs = [d for d in docs if d.scope == DocumentScope.CHAT and d.conversation_id == conversation_id]
    elif scope == "all_for_chat" and conversation_id:
        docs = [
            d for d in docs
            if d.scope == DocumentScope.LIBRARY
            or (d.scope == DocumentScope.CHAT and d.conversation_id == conversation_id)
        ]

    return [
        DocumentInfo(
            id=doc.id,
            filename=doc.filename,
            file_type=doc.file_type,
            page_count=doc.page_count,
            file_size=doc.file_size,
            status=doc.status,
            scope=doc.scope,
            conversation_id=doc.conversation_id,
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
        file_type=doc.file_type,
        page_count=doc.page_count,
        file_size=doc.file_size,
        status=doc.status,
        scope=doc.scope,
        conversation_id=doc.conversation_id,
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
        raise HTTPException(status_code=404, detail="File not found on disk")

    # Determine content type
    ext = file_path.suffix.lower()
    mime_map = {
        ".pdf": "application/pdf",
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".bmp": "image/bmp",
        ".tiff": "image/tiff", ".tif": "image/tiff",
        ".webp": "image/webp",
    }
    media_type = mime_map.get(ext, "application/octet-stream")

    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=doc.filename,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
        },
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
