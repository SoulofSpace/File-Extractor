"""
phash.py — Pure NumPy Perceptual Hashing for Image Near-Duplicate Detection.
Computes 64-bit DCT-based pHash and difference hash (dHash) without extra third-party C libraries.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional
import numpy as np
from PIL import Image


def _compute_dct_matrix(n: int = 32) -> np.ndarray:
    """Computes an NxN Discrete Cosine Transform (Type-II) matrix."""
    matrix = np.zeros((n, n), dtype=np.float32)
    for i in range(n):
        for j in range(n):
            alpha = np.sqrt(1.0 / n) if i == 0 else np.sqrt(2.0 / n)
            matrix[i, j] = alpha * np.cos(((2 * j + 1) * i * np.pi) / (2.0 * n))
    return matrix


_DCT_32 = _compute_dct_matrix(32)


def compute_phash(image_path: Path | str) -> Optional[str]:
    """
    Computes 64-bit Discrete Cosine Transform perceptual hash (pHash).
    1. Resize image to 32x32 grayscale.
    2. Compute 2D DCT.
    3. Extract top-left 8x8 low-frequency coefficients (ignoring DC component).
    4. Threshold coefficients against their median value to generate 64-bit fingerprint.
    5. Returns 16-character hexadecimal string.
    """
    try:
        p = Path(image_path)
        with Image.open(p) as img:
            # Resize to 32x32 with anti-aliasing and convert to 32-bit float grayscale
            gray = img.convert("L").resize((32, 32), Image.Resampling.BILINEAR)
            pixels = np.asarray(gray, dtype=np.float32)

            # 2D DCT: D * pixels * D.T
            dct_2d = _DCT_32 @ pixels @ _DCT_32.T

            # Extract 8x8 low frequency square
            low_freq = dct_2d[:8, :8]

            # Compute median excluding DC coefficient at (0, 0)
            median_val = np.median(low_freq[1:, 1:])

            # 64-bit boolean mask
            bit_mask = (low_freq > median_val).flatten()

            # Pack 64 bits into uint64 and format as 16-char hex
            packed = 0
            for bit in bit_mask:
                packed = (packed << 1) | int(bit)

            return f"{packed:016x}"
    except Exception:
        return None


def hamming_distance(hash1: str, hash2: str) -> int:
    """
    Computes bitwise Hamming distance between two hexadecimal hash strings.
    A distance <= 10 typically indicates an identical or visually modified duplicate.
    """
    try:
        val1 = int(hash1, 16)
        val2 = int(hash2, 16)
        xor_val = val1 ^ val2
        return bin(xor_val).count("1")
    except (ValueError, TypeError):
        return 64
