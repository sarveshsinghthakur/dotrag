import json
from datetime import datetime
from typing import Optional
from app.models import Document, DocumentChunk, Conversation, Message, DocumentStatus, DocumentScope


class DatabaseService:
    """In-memory database with optional JSON persistence."""

    def __init__(self, db_path: str = "dotrag_db.json"):
        self.db_path = db_path
        self._in_memory = db_path == ":memory:"
        self.documents: dict[str, Document] = {}
        self.chunks: dict[str, DocumentChunk] = {}
        self.conversations: dict[str, Conversation] = {}
        self.messages: dict[str, Message] = {}
        if not self._in_memory:
            self._load()

    def _load(self):
        if self._in_memory:
            return
        try:
            with open(self.db_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for d in data.get("documents", []):
                try:
                    doc = Document(**d)
                    self.documents[doc.id] = doc
                except Exception:
                    pass
            for c in data.get("chunks", []):
                try:
                    chunk = DocumentChunk(**c)
                    self.chunks[chunk.id] = chunk
                except Exception:
                    pass
            for conv in data.get("conversations", []):
                try:
                    conversation = Conversation(**conv)
                    self.conversations[conversation.id] = conversation
                except Exception:
                    pass
            for msg in data.get("messages", []):
                try:
                    message = Message(**msg)
                    self.messages[message.id] = message
                except Exception:
                    pass
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    def _save(self):
        if self._in_memory:
            return
        import os
        data = {
            "documents": [d.model_dump(mode="json") for d in self.documents.values()],
            "chunks": [c.model_dump(mode="json") for c in self.chunks.values()],
            "conversations": [c.model_dump(mode="json") for c in self.conversations.values()],
            "messages": [m.model_dump(mode="json") for m in self.messages.values()],
        }
        tmp_path = self.db_path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, default=str, ensure_ascii=False)
        os.replace(tmp_path, self.db_path)

    # ──────────────────── Documents ────────────────────

    def create_document(self, doc: Document) -> Document:
        self.documents[doc.id] = doc
        self._save()
        return doc

    def get_document(self, doc_id: str) -> Optional[Document]:
        return self.documents.get(doc_id)

    def list_documents(self) -> list[Document]:
        return sorted(self.documents.values(), key=lambda d: d.created_at, reverse=True)

    def list_library_documents(self) -> list[Document]:
        """Return only LIBRARY-scoped documents."""
        return [d for d in self.list_documents() if d.scope == DocumentScope.LIBRARY]

    def list_documents_for_chat(self, conversation_id: str) -> list[Document]:
        """Return LIBRARY docs + docs scoped to this specific chat."""
        return [
            d for d in self.list_documents()
            if d.scope == DocumentScope.LIBRARY
            or (d.scope == DocumentScope.CHAT and d.conversation_id == conversation_id)
        ]

    def update_document(self, doc_id: str, **kwargs) -> Optional[Document]:
        doc = self.documents.get(doc_id)
        if not doc:
            return None
        for key, value in kwargs.items():
            if hasattr(doc, key):
                setattr(doc, key, value)
        doc.updated_at = datetime.utcnow()
        self._save()
        return doc

    def delete_document(self, doc_id: str) -> bool:
        if doc_id not in self.documents:
            return False
        del self.documents[doc_id]
        self.chunks = {k: v for k, v in self.chunks.items() if v.document_id != doc_id}
        self._save()
        return True

    # ──────────────────── Chunks ────────────────────

    def create_chunk(self, chunk: DocumentChunk) -> DocumentChunk:
        self.chunks[chunk.id] = chunk
        return chunk

    def get_chunks_by_document(self, doc_id: str) -> list[DocumentChunk]:
        return sorted(
            [c for c in self.chunks.values() if c.document_id == doc_id],
            key=lambda c: (c.page_number, c.chunk_index),
        )

    def get_chunk(self, chunk_id: str) -> Optional[DocumentChunk]:
        return self.chunks.get(chunk_id)

    def bulk_create_chunks(self, chunks: list[DocumentChunk]):
        for chunk in chunks:
            self.chunks[chunk.id] = chunk
        self._save()

    # ──────────────────── Conversations ────────────────────

    def create_conversation(self, conv: Conversation) -> Conversation:
        self.conversations[conv.id] = conv
        self._save()
        return conv

    def get_conversation(self, conv_id: str) -> Optional[Conversation]:
        return self.conversations.get(conv_id)

    def list_conversations(self) -> list[Conversation]:
        return sorted(self.conversations.values(), key=lambda c: c.updated_at, reverse=True)

    def update_conversation(self, conv_id: str, **kwargs) -> Optional[Conversation]:
        conv = self.conversations.get(conv_id)
        if not conv:
            return None
        for key, value in kwargs.items():
            if hasattr(conv, key):
                setattr(conv, key, value)
        conv.updated_at = datetime.utcnow()
        self._save()
        return conv

    # ──────────────────── Messages ────────────────────

    def create_message(self, msg: Message) -> Message:
        self.messages[msg.id] = msg
        self._save()
        return msg

    def get_messages_by_conversation(self, conv_id: str, limit: int = 50) -> list[Message]:
        msgs = [m for m in self.messages.values() if m.conversation_id == conv_id]
        return sorted(msgs, key=lambda m: m.created_at)[-limit:]

    # ──────────────────── Maintenance ────────────────────

    def cleanup(self):
        self.documents.clear()
        self.chunks.clear()
        self.conversations.clear()
        self.messages.clear()
        self._save()


_db_instance: Optional[DatabaseService] = None


def get_db() -> DatabaseService:
    global _db_instance
    if _db_instance is None:
        _db_instance = DatabaseService()
    return _db_instance
