"""
duplicates.py — Duplicate and Near-Duplicate Detection Engine for FILE XTRACTOR V2.
Detects:
  • Exact duplicates across all file types via streamed cryptographic SHA-256
  • Near-duplicate images via 64-bit DCT perceptual hash (pHash) Hamming distance
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List
from .phash import hamming_distance
from ..database import Database


def get_exact_duplicate_groups(db: Database) -> List[Dict[str, Any]]:
    """
    Returns groups of files that have identical SHA-256 content hashes.
    Output: [{'sha256': '...', 'count': 2, 'files': ['path1', 'path2']}, ...]
    """
    rows = db.find_exact_duplicates()
    groups = []
    for r in rows:
        paths = [p for p in r["paths"].split("|||") if p]
        groups.append({
            "sha256": r["sha256_hash"],
            "copy_count": r["copy_count"],
            "file_paths": paths,
        })
    return groups


def get_near_duplicate_images(
    db: Database,
    max_hamming_distance: int = 8,
) -> List[Dict[str, Any]]:
    """
    Compares perceptual hashes across indexed images to find visually similar or resized copies.
    """
    with db.connection() as conn:
        rows = conn.execute(
            """
            SELECT id, filename, path, phash, size_bytes
            FROM files
            WHERE phash IS NOT NULL AND phash != ''
            ORDER BY id ASC
            """
        ).fetchall()

    items = [dict(r) for r in rows]
    matches = []

    for i in range(len(items)):
        h1 = items[i]["phash"]
        for j in range(i + 1, len(items)):
            h2 = items[j]["phash"]
            dist = hamming_distance(h1, h2)
            if dist <= max_hamming_distance:
                matches.append({
                    "distance": dist,
                    "similarity_pct": int(round((1.0 - (dist / 64.0)) * 100)),
                    "image_a": items[i],
                    "image_b": items[j],
                })

    matches.sort(key=lambda x: x["distance"])
    return matches
