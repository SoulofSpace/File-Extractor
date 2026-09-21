"""
format_normalizer.py — Unified file representation normalizer for FILE XTRACTOR V3.
Converts heterogeneous input files (images, scanned PDFs) into standardized PIL Images
for visual understanding and OCR preprocessing.
"""

from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import Optional
from PIL import Image, ImageOps

logger = logging.getLogger(__name__)

SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".gif"}


class FormatNormalizer:
    """Standardizes documents and images into uniform PIL Image representations."""

    @staticmethod
    def is_visual_candidate(path: Path | str) -> bool:
        """Determine if a file can be processed visually."""
        ext = Path(path).suffix.lower()
        return ext in SUPPORTED_IMAGE_EXTENSIONS or ext == ".pdf"

    @classmethod
    def load_as_image(cls, path: Path | str, max_dimension: int = 1920) -> Optional[Image.Image]:
        """
        Loads a file as a normalized PIL Image in RGB format.
        Applies EXIF rotation correction and dimensions scaling.
        """
        file_path = Path(path)
        if not file_path.exists() or not file_path.is_file():
            return None

        ext = file_path.suffix.lower()

        if ext in SUPPORTED_IMAGE_EXTENSIONS:
            return cls._load_image_file(file_path, max_dimension)
        elif ext == ".pdf":
            return cls._load_pdf_first_page(file_path, max_dimension)

        return None

    @staticmethod
    def _load_image_file(file_path: Path, max_dimension: int) -> Optional[Image.Image]:
        try:
            with Image.open(file_path) as raw_img:
                # Correct orientation from EXIF tags
                img = ImageOps.exif_transpose(raw_img)
                if img.mode != "RGB":
                    img = img.convert("RGB")

                # Scale down if gigantic to protect memory
                width, height = img.size
                if max(width, height) > max_dimension:
                    scale = max_dimension / max(width, height)
                    new_size = (int(width * scale), int(height * scale))
                    img = img.resize(new_size, Image.Resampling.LANCZOS)
                else:
                    img = img.copy()

                return img
        except Exception as exc:
            logger.warning("Failed to load image %s: %s", file_path, exc)
            return None

    @staticmethod
    def _load_pdf_first_page(file_path: Path, max_dimension: int) -> Optional[Image.Image]:
        """Extract first page image from PDF if available via pypdf."""
        try:
            import pypdf
            reader = pypdf.PdfReader(str(file_path))
            if not reader.pages:
                return None

            page0 = reader.pages[0]
            if hasattr(page0, "images") and len(page0.images) > 0:
                # Pick the largest image by byte size
                best_img_file = max(page0.images, key=lambda img: len(img.data))
                img = Image.open(io.BytesIO(best_img_file.data))
                img = ImageOps.exif_transpose(img)
                if img.mode != "RGB":
                    img = img.convert("RGB")

                width, height = img.size
                if max(width, height) > max_dimension:
                    scale = max_dimension / max(width, height)
                    new_size = (int(width * scale), int(height * scale))
                    img = img.resize(new_size, Image.Resampling.LANCZOS)
                else:
                    img = img.copy()

                return img
        except Exception as exc:
            logger.debug("PDF page image extraction skipped for %s: %s", file_path, exc)

        return None
