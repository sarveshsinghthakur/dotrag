import re
import base64
from pathlib import Path
from typing import Optional
import fitz  # PyMuPDF


SUPPORTED_IMAGE_TYPES = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif", ".webp"}
SUPPORTED_DOC_TYPES = {".pdf"} | SUPPORTED_IMAGE_TYPES


class FileLoader:
    """Extract text from PDF files and images.

    - PDFs: page-by-page text extraction with OCR fallback for scanned pages.
    - Images: OCR via PyMuPDF pixmap → description text, plus Mistral vision as
      a fallback if available (requires the chat model to be vision-capable).
    """

    # ─────────────────────── public entry point ───────────────────────────────

    async def extract_pages(self, file_path: str) -> list[dict]:
        """Return a list of page dicts: {page_number, content, metadata}."""
        path = Path(file_path)
        suffix = path.suffix.lower()

        if suffix == ".pdf":
            return await self._extract_pdf(file_path)
        elif suffix in SUPPORTED_IMAGE_TYPES:
            return await self._extract_image(file_path)
        else:
            raise ValueError(f"Unsupported file type: {suffix}")

    # ─────────────────────── PDF extraction ───────────────────────────────────

    async def _extract_pdf(self, file_path: str) -> list[dict]:
        pages = []
        doc = fitz.open(file_path)

        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text("text")

            # If the page looks scanned, try OCR
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
                            "source_type": "pdf",
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
        """OCR fallback for scanned pages using PyMuPDF's built-in OCR."""
        try:
            text = page.get_text("ocr")
            return text if text else ""
        except Exception:
            # Fallback: render to image and attempt vision description
            try:
                pix = page.get_pixmap(dpi=150)
                img_bytes = pix.tobytes("png")
                return await self._describe_image_bytes(img_bytes, "scanned_page")
            except Exception:
                return ""

    # ─────────────────────── Image extraction ─────────────────────────────────

    async def _extract_image(self, file_path: str) -> list[dict]:
        """Extract content from a standalone image file."""
        try:
            # Try opening with PyMuPDF (works for many image formats)
            doc = fitz.open(file_path)
            page = doc[0]
            pix = page.get_pixmap(dpi=150)
            img_bytes = pix.tobytes("png")
            doc.close()
        except Exception:
            # Fallback: read raw bytes
            with open(file_path, "rb") as f:
                img_bytes = f.read()

        description = await self._describe_image_bytes(img_bytes, Path(file_path).name)

        if description.strip():
            return [
                {
                    "page_number": 1,
                    "content": description.strip(),
                    "metadata": {
                        "source_type": "image",
                        "original_filename": Path(file_path).name,
                    },
                }
            ]
        return []

    async def _describe_image_bytes(self, img_bytes: bytes, label: str = "image") -> str:
        """Use Mistral vision model (if available) or return a placeholder."""
        try:
            import httpx
            from app.config import settings
            from app.services.mistral import get_mistral_service

            svc = get_mistral_service()
            b64 = base64.b64encode(img_bytes).decode()

            # Build a vision message (Mistral pixtral models support image_url)
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Please extract and transcribe ALL text visible in this image. "
                                "If this is a document page, reproduce its full text content. "
                                "If it's a diagram or photo, describe it in detail."
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{b64}"},
                        },
                    ],
                }
            ]

            async with httpx.AsyncClient(
                base_url=svc.base_url,
                headers={
                    "Authorization": f"Bearer {svc.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=httpx.Timeout(60.0, connect=10.0),
            ) as client:
                # Try pixtral-12b first, fall back to regular chat model
                for model in ["pixtral-12b-2409", svc.chat_model]:
                    try:
                        resp = await client.post(
                            "/chat/completions",
                            json={
                                "model": model,
                                "messages": messages,
                                "max_tokens": 2048,
                            },
                        )
                        if resp.status_code == 200:
                            data = resp.json()
                            content = data["choices"][0]["message"].get("content", "")
                            if content:
                                return f"[Image: {label}]\n{content}"
                    except Exception:
                        continue

        except Exception:
            pass

        # Graceful fallback — at least record that we have an image
        return f"[Image file: {label}]\nThis file contains image content that could not be automatically transcribed."

    # ─────────────────────── text cleaning ────────────────────────────────────

    def _clean_text(self, text: str) -> str:
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r" {2,}", " ", text)
        text = re.sub(r"\x00", "", text)
        return text.strip()


# Backward-compatible alias
PDFLoader = FileLoader
