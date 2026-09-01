import uuid
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class DocumentStatus(str, Enum):
    UPLOADING = "uploading"
    PROCESSING = "processing"
    INDEXING = "indexing"
    READY = "ready"
    ERROR = "error"


class Document(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    filename: str
    file_path: str
    page_count: int = 0
    file_size: int = 0
    status: DocumentStatus = DocumentStatus.UPLOADING
    error_message: Optional[str] = None
    metadata: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class DocumentChunk(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    document_id: str
    page_number: int
    chunk_index: int
    content: str
    embedding_id: Optional[str] = None
    metadata: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Conversation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str = "New Conversation"
    document_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class Message(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    conversation_id: str
    role: MessageRole
    content: str
    citations: list["Citation"] = Field(default_factory=list)
    tool_executions: list["ToolExecution"] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Citation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    message_id: str = ""
    document_id: str
    document_name: str
    page_number: int
    chunk_id: Optional[str] = None
    text_snippet: str = ""
    relevance_score: float = 0.0
    citation_index: int = 0


class SearchResult(BaseModel):
    chunk_id: str
    document_id: str
    document_name: str
    page_number: int
    content: str
    score: float
    metadata: dict = Field(default_factory=dict)


class ToolExecution(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tool_name: str
    input_data: dict = Field(default_factory=dict)
    output_data: dict = Field(default_factory=dict)
    status: str = "pending"
    duration_ms: float = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)


# Request/Response models
class UploadResponse(BaseModel):
    document: Document
    message: str


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    document_ids: list[str] = Field(default_factory=list)


class ChatResponse(BaseModel):
    response: str
    conversation_id: str
    citations: list[Citation] = Field(default_factory=list)
    tool_executions: list[ToolExecution] = Field(default_factory=list)


class SearchRequest(BaseModel):
    query: str
    document_ids: list[str] = Field(default_factory=list)
    page_numbers: list[int] = Field(default_factory=list)
    top_k: int = 8


class SearchResponse(BaseModel):
    results: list[SearchResult]
    query: str
    total_results: int


class SummarizeRequest(BaseModel):
    document_id: str
    section_page_start: Optional[int] = None
    section_page_end: Optional[int] = None


class CompareRequest(BaseModel):
    document_ids: list[str]
    topic: Optional[str] = None


class DocumentInfo(BaseModel):
    id: str
    filename: str
    page_count: int
    file_size: int
    status: DocumentStatus
    created_at: datetime
    chunk_count: int = 0
