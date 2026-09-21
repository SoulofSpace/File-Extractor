"""
extractors.py — Multi-format Text and OCR Extraction
Supports documents, code, spreadsheets, scanned PDFs, and standalone images.
Guarantees zero unhandled exceptions: any unreadable or corrupted file gracefully returns empty text.
"""

from __future__ import annotations

from pathlib import Path
from typing import Tuple

from .ocr import ocr_image, ocr_pdf_images, is_ocr_available

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".gif"}
TEXT_EXTENSIONS = {
    ".txt", ".md", ".json", ".csv", ".py", ".js", ".ts", ".html",
    ".css", ".xml", ".yaml", ".yml", ".c", ".cpp", ".java", ".sql",
}


def extract_file_content(path: Path) -> Tuple[str, str]:
    """
    Extracts content from a file, returning a tuple of:
      (extracted_text, ocr_text)
    Guaranteed never to raise exceptions.
    """
    try:
        if not path.is_file() or path.stat().st_size == 0:
            return ("", "")

        ext = path.suffix.lower()

        # 1. Plain text and source code
        if ext in TEXT_EXTENSIONS:
            try:
                # Try UTF-8 first, fallback to Latin-1 with replacement
                text = path.read_text(encoding="utf-8", errors="replace")
                return (text, "")
            except Exception:
                try:
                    text = path.read_text(encoding="latin-1", errors="replace")
                    return (text, "")
                except Exception:
                    return ("", "")

        # 2. Microsoft Word documents (.docx)
        if ext == ".docx":
            try:
                from docx import Document
                doc = Document(path)
                paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
                return ("\n".join(paragraphs), "")
            except Exception:
                return ("", "")

        # 3. PDF Documents (Native digital text + OCR for scanned pages/images)
        if ext == ".pdf":
            native_text = ""
            ocr_text = ""
            try:
                from pypdf import PdfReader
                reader = PdfReader(path)
                extracted_pages: list[str] = []
                for page in reader.pages:
                    try:
                        p_txt = page.extract_text()
                        if p_txt:
                            extracted_pages.append(p_txt)
                    except Exception:
                        continue
                native_text = "\n".join(extracted_pages).strip()
            except Exception:
                native_text = ""

            # If native text is very sparse (< 50 chars) or PDF has embedded images, run OCR
            if is_ocr_available() and len(native_text) < 100:
                try:
                    ocr_text = ocr_pdf_images(path, max_pages=20)
                except Exception:
                    ocr_text = ""

            return (native_text, ocr_text)

        # 4. Standalone Images (.png, .jpg, .jpeg, .webp, .bmp, .tiff)
        if ext in IMAGE_EXTENSIONS:
            if is_ocr_available():
                try:
                    ocr_text = ocr_image(path)
                    return ("", ocr_text)
                except Exception:
                    return ("", "")
            return ("", "")

        return ("", "")

    except Exception:
        # Ultimate safety fallback for any unexpected system or filesystem condition
        return ("", "")


def extract_text(path: Path) -> str:
    """Legacy backward-compatible text extractor returning combined text."""
    native, ocr = extract_file_content(path)
    if native and ocr:
        return f"{native}\n\n[OCR Text]:\n{ocr}"
    return native or ocr
