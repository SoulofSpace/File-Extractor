"""
ocr.py — Accurate OCR Engine for Images & Scanned Documents
Uses Tesseract 5.5.0 and Pillow to extract high-accuracy text from:
  • Standalone images (.png, .jpg, .jpeg, .webp, .bmp, .tiff)
  • Embedded images in PDFs and scanned PDF pages
Includes automatic preprocessing (contrast enhancement, grayscale, scaling)
and robust exception handling so OCR never crashes the application.
"""

from __future__ import annotations

import io
import os
import shutil
from pathlib import Path
from typing import Optional

try:
    from PIL import Image, ImageEnhance, ImageFilter
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import pytesseract
    PYTESSERACT_AVAILABLE = True
except ImportError:
    PYTESSERACT_AVAILABLE = False

import threading

# Strictly throttle concurrent Tesseract subprocesses to <= 2 to prevent CPU saturation
_OCR_SEMAPHORE = threading.BoundedSemaphore(2)


def _find_tesseract_cmd() -> Optional[str]:
    """Finds the Tesseract executable path on Windows or POSIX."""
    candidates = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    found = shutil.which("tesseract")
    if found:
        return found
    return None


# Configure pytesseract path once
_TESSERACT_CMD = _find_tesseract_cmd()
if _TESSERACT_CMD and PYTESSERACT_AVAILABLE:
    pytesseract.pytesseract.tesseract_cmd = _TESSERACT_CMD


def is_ocr_available() -> bool:
    """Returns True if Pillow, pytesseract, and Tesseract binary are ready."""
    return PIL_AVAILABLE and PYTESSERACT_AVAILABLE and (_TESSERACT_CMD is not None)


def preprocess_image(image: Image.Image) -> Image.Image:
    """
    Optimizes image for Tesseract OCR:
      • Converts RGBA / Palette to RGB
      • Converts to Grayscale (L)
      • Upscales small images so font height >= 20-30px for high accuracy
      • Enhances contrast for clearer character separation
    """
    # Normalize color mode
    if image.mode in ("RGBA", "LA", "P"):
        background = Image.new("RGB", image.size, (255, 255, 255))
        if image.mode == "RGBA":
            background.paste(image, mask=image.split()[-1])
        else:
            background.paste(image.convert("RGB"))
        image = background
    elif image.mode != "RGB":
        image = image.convert("RGB")

    # Upscale tiny images (< 800px width/height) for higher OCR precision
    w, h = image.size
    if w > 0 and h > 0 and (w < 800 or h < 600):
        scale = max(1.5, min(3.0, 1200 / max(w, h)))
        image = image.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)

    # Convert to grayscale
    gray = image.convert("L")

    # Enhance contrast
    enhancer = ImageEnhance.Contrast(gray)
    enhanced = enhancer.enhance(1.8)

    return enhanced


def ocr_image(image_path: Path | str, timeout_seconds: int = 15) -> str:
    """
    Extracts text from an image file using Tesseract OCR.
    Safely returns an empty string on any error without throwing.
    """
    if not is_ocr_available():
        return ""

    try:
        path = Path(image_path)
        if not path.is_file() or path.stat().st_size == 0:
            return ""

        with Image.open(path) as img:
            processed = preprocess_image(img)
            # PSM 3 (Fully automatic page segmentation) with English, throttled via semaphore
            with _OCR_SEMAPHORE:
                text = pytesseract.image_to_string(
                    processed,
                    lang="eng",
                    config="--psm 3 --oem 1",
                    timeout=timeout_seconds,
                )
            return text.strip()
    except Exception:
        # Gracefully handle corrupted images, unsupported formats, or OCR timeouts
        return ""


def ocr_image_data(raw_bytes: bytes, timeout_seconds: int = 10) -> str:
    """Extracts text from raw image bytes in memory (e.g. from PDF stream)."""
    if not is_ocr_available() or not raw_bytes:
        return ""

    try:
        with Image.open(io.BytesIO(raw_bytes)) as img:
            # Skip tiny decorative icons / 1x1 tracking pixels (< 50x50)
            if img.width < 50 or img.height < 50:
                return ""
            processed = preprocess_image(img)
            with _OCR_SEMAPHORE:
                text = pytesseract.image_to_string(
                    processed,
                    lang="eng",
                    config="--psm 3 --oem 1",
                    timeout=timeout_seconds,
                )
            return text.strip()
    except Exception:
        return ""


def ocr_pdf_images(pdf_path: Path | str, max_pages: int = 20) -> str:
    """
    Extracts embedded images from up to `max_pages` of a PDF and runs OCR on them.
    Ideal for scanned PDFs or PDFs containing receipts/invoices/diagrams.
    """
    if not is_ocr_available():
        return ""

    try:
        from pypdf import PdfReader
        path = Path(pdf_path)
        reader = PdfReader(path)
        extracted_chunks: list[str] = []

        total_pages = min(len(reader.pages), max_pages)
        for page_idx in range(total_pages):
            page = reader.pages[page_idx]
            # Safely iterate page images
            try:
                images = getattr(page, "images", [])
                for img_obj in images:
                    try:
                        raw_data = getattr(img_obj, "data", None)
                        if raw_data:
                            chunk = ocr_image_data(raw_data)
                            if chunk:
                                extracted_chunks.append(chunk)
                    except Exception:
                        continue
            except Exception:
                continue

        return "\n\n".join(extracted_chunks).strip()
    except Exception:
        return ""
