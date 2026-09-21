"""
hashing.py — Cryptographic and fast-path hashing for FILE XTRACTOR V2.
Implements streamed chunked SHA-256 hashing and (size, mtime) fast-path validation.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Optional, Tuple

from .interfaces import FileIdentity

DEFAULT_CHUNK_SIZE = 65536  # 64 KB chunks for memory safety


def fast_mtime_size_check(
    file_path: Path | str,
    cached_size: int,
    cached_mtime: float,
    tolerance: float = 1e-4,
) -> bool:
    """
    Fast-path pre-check to detect unmodified files without reading content.
    Returns True if file size and modification time match cached values.
    """
    try:
        p = Path(file_path)
        stat = p.stat()
        return stat.st_size == cached_size and abs(stat.st_mtime - cached_mtime) < tolerance
    except (OSError, ValueError):
        return False


def compute_sha256(file_path: Path | str, chunk_size: int = DEFAULT_CHUNK_SIZE) -> Optional[str]:
    """
    Computes full SHA-256 hash by streaming file in chunks.
    Safe for multi-gigabyte files; never buffers full file in memory.
    Returns 64-character lowercase hex string or None if unreadable.
    """
    try:
        p = Path(file_path)
        hasher = hashlib.sha256()
        with open(p, "rb") as f:
            while chunk := f.read(chunk_size):
                hasher.update(chunk)
        return hasher.hexdigest()
    except (OSError, PermissionError):
        return None


def get_file_identity(
    file_path: Path | str,
    compute_hash: bool = True,
) -> Optional[FileIdentity]:
    """
    Constructs a FileIdentity record with size, mtime, and optional streamed SHA-256.
    """
    try:
        p = Path(file_path).resolve()
        stat = p.stat()
        sha = compute_sha256(p) if compute_hash else None
        return FileIdentity(
            path=p,
            size_bytes=stat.st_size,
            modified_at=stat.st_mtime,
            sha256_hash=sha,
        )
    except (OSError, PermissionError):
        return None
