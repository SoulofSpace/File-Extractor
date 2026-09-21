"""
layout_ocr.py — Layout-aware display text and header extraction for FILE XTRACTOR V3.
Complements monolithic page-segmentation OCR by isolating high-contrast display regions
and running multi-pass OCR for stylized titles, banners, and artistic typography.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

from .ocr import is_ocr_available, _OCR_SEMAPHORE, _find_tesseract_cmd

logger = logging.getLogger(__name__)

try:
    import pytesseract
except ImportError:
    pytesseract = None


class LayoutAwareOCR:
    """
    Multi-pass OCR engine with region and display-text awareness.
    Recovers stylized headers, event titles, banners, and dispersed text
    that standard single-pass monolithic OCR (--psm 3) misses.
    """

    @classmethod
    def extract_layout_text(cls, image: Image.Image, timeout_seconds: int = 15) -> str:
        """
        Executes dual-pass OCR:
          Pass 1: Automatic page segmentation (--psm 3) on enhanced grayscale.
          Pass 2: Sparse display text extraction (--psm 11) on high-contrast thresholded image.
        Merges results while eliminating duplicate lines.
        """
        if not is_ocr_available() or pytesseract is None:
            return ""

        extracted_lines: List[str] = []
        seen_lines = set()

        def _add_line(line: str) -> None:
            clean = line.strip()
            if len(clean) >= 2 and clean.lower() not in seen_lines:
                seen_lines.add(clean.lower())
                extracted_lines.append(clean)

        # Pass 1: Standard layout pass (--psm 3)
        try:
            p1_img = cls._prepare_pass1(image)
            with _OCR_SEMAPHORE:
                t1 = pytesseract.image_to_string(
                    p1_img,
                    lang="eng",
                    config="--psm 3 --oem 1",
                    timeout=timeout_seconds,
                )
            for l in t1.splitlines():
                _add_line(l)
        except Exception as exc:
            logger.debug("Pass 1 OCR error: %s", exc)

        # Pass 2: High-contrast sparse text pass (--psm 11) for artistic / poster headers
        try:
            p2_img = cls._prepare_pass2(image)
            with _OCR_SEMAPHORE:
                t2 = pytesseract.image_to_string(
                    p2_img,
                    lang="eng",
                    config="--psm 11 --oem 1",
                    timeout=timeout_seconds,
                )
            for l in t2.splitlines():
                _add_line(l)
        except Exception as exc:
            logger.debug("Pass 2 OCR error: %s", exc)

        return "\n".join(extracted_lines).strip()

    @classmethod
    def extract_from_path(cls, path: Path | str, timeout_seconds: int = 15) -> str:
        """Helper to run layout-aware OCR directly from a file path."""
        try:
            with Image.open(path) as img:
                return cls.extract_layout_text(img, timeout_seconds=timeout_seconds)
        except Exception as exc:
            logger.debug("Failed layout OCR for %s: %s", path, exc)
            return ""

    @staticmethod
    def _prepare_pass1(image: Image.Image) -> Image.Image:
        """Standard grayscale and contrast enhancement."""
        if image.mode != "RGB":
            image = image.convert("RGB")
        gray = image.convert("L")
        return ImageEnhance.Contrast(gray).enhance(1.8)

    @staticmethod
    def _prepare_pass2(image: Image.Image) -> Image.Image:
        """High-contrast binarization and edge sharpness for stylized display banners."""
        if image.mode != "RGB":
            image = image.convert("RGB")
        gray = image.convert("L")
        # Enhance sharpness and contrast dramatically
        sharpened = gray.filter(ImageFilter.SHARPEN)
        contrast = ImageEnhance.Contrast(sharpened).enhance(2.5)
        # Binarize with midpoint threshold
        threshold = 140
        return contrast.point(lambda p: 255 if p > threshold else 0)
