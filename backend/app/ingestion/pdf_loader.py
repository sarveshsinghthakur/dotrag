import re
from pathlib import Path
from typing import Optional
import fitz  # PyMuPDF


class PDFLoader:
    """Extract text from PDF files with OCR fallback."""

    async def extract_pages(self, file_path: str) -> list[dict]:
        pages = []
        doc = fitz.open(file_path)

        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text("text")

            # Check if page has meaningful text
            if self._is_scanned_page(text):
                text = await self._ocr_page(page)

            text = self._clean_text(text)
            if text.strip():
                pages.append(
                    {
                        "page_number": page_num + 1,
                        "content": text.strip(),
                        "metadata": {
                            "page_width": page.rect.width,
                            "page_height": page.rect.height,
                        },
                    }
                )

        doc.close()
        return pages

    def _is_scanned_page(self, text: str) -> bool:
        """Detect if a page appears to be scanned (very little text)."""
        cleaned = re.sub(r"\s+", "", text)
        return len(cleaned) < 50

    async def _ocr_page(self, page) -> str:
        """OCR fallback for scanned pages."""
        try:
            # Use PyMuPDF's built-in OCR if available
            # For production, integrate Tesseract or cloud OCR
            text = page.get_text("ocr")
            return text if text else ""
        except Exception:
            return ""

    def _clean_text(self, text: str) -> str:
        """Clean extracted text."""
        # Remove excessive whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r" {2,}", " ", text)
        # Remove common PDF artifacts
        text = re.sub(r"\x00", "", text)
        return text.strip()
