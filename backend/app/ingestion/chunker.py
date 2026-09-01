import re
from app.models import DocumentChunk


class DocumentChunker:
    """Intelligent document chunking with page awareness."""

    def __init__(self, chunk_size: int = 1024, chunk_overlap: int = 256):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_pages(
        self, pages: list[dict], document_id: str, filename: str
    ) -> list[DocumentChunk]:
        all_chunks = []
        global_index = 0

        for page_data in pages:
            page_num = page_data["page_number"]
            content = page_data["content"]

            page_chunks = self._chunk_text(content)
            for chunk_text in page_chunks:
                chunk = DocumentChunk(
                    document_id=document_id,
                    page_number=page_num,
                    chunk_index=global_index,
                    content=chunk_text,
                    metadata={
                        "filename": filename,
                        "page_number": page_num,
                        "chunk_index": global_index,
                    },
                )
                all_chunks.append(chunk)
                global_index += 1

        return all_chunks

    def _chunk_text(self, text: str) -> list[str]:
        """Split text into chunks respecting paragraph and sentence boundaries."""
        if len(text) <= self.chunk_size:
            return [text]

        chunks = []
        paragraphs = re.split(r"\n\n+", text)
        current_chunk = ""

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # If adding this paragraph exceeds chunk size
            if len(current_chunk) + len(para) + 2 > self.chunk_size:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    # Keep overlap
                    overlap_text = self._get_overlap(current_chunk)
                    current_chunk = overlap_text + "\n\n" + para
                else:
                    # Single paragraph is too large, split by sentences
                    sentence_chunks = self._split_by_sentences(para)
                    chunks.extend(sentence_chunks[:-1])
                    current_chunk = sentence_chunks[-1] if sentence_chunks else ""
            else:
                current_chunk = current_chunk + "\n\n" + para if current_chunk else para

        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        return chunks

    def _get_overlap(self, text: str) -> str:
        """Get the last portion of text for overlap."""
        if len(text) <= self.chunk_overlap:
            return text
        # Try to break at a sentence boundary
        overlap_start = len(text) - self.chunk_overlap
        sentence_break = text.rfind(".", overlap_start, len(text))
        if sentence_break > overlap_start:
            return text[sentence_break + 1 :].strip()
        return text[overlap_start:].strip()

    def _split_by_sentences(self, text: str) -> list[str]:
        """Split large text by sentence boundaries."""
        sentences = re.split(r"(?<=[.!?])\s+", text)
        chunks = []
        current = ""

        for sentence in sentences:
            if len(current) + len(sentence) + 1 > self.chunk_size:
                if current:
                    chunks.append(current.strip())
                current = sentence
            else:
                current = current + " " + sentence if current else sentence

        if current.strip():
            chunks.append(current.strip())

        return chunks if chunks else [text]
