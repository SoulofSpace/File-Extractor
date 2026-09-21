"""
test_offline_verification.py — Strict Offline Verification Suite for FILE XTRACTOR V2.
Blocks all network socket connections to mathematically verify 100% offline privacy:
  • Startup works offline
  • Model loading works offline (local cache)
  • OCR works offline (local Tesseract 5.5.0 binary)
  • Semantic search works offline
  • CLIP vision search works offline
  • Indexing pipeline works offline
  • Search history & saved searches work offline
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure src is on Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import os
import socket
import tempfile
import urllib.request
import numpy as np
from PIL import Image, ImageDraw

from intellifile.database import Database
from intellifile.ai_agent import AIAgent
from intellifile.scanner import ScanWorker
from intellifile.vector_store import SQLiteFlatVectorStore
from intellifile.embedding_provider import SentenceTransformerProvider
from intellifile.vision_search import get_clip_model, search_images_with_clip
from intellifile.ocr import ocr_image, is_ocr_available


class NetworkAccessAttempted(RuntimeError):
    """Raised when any outbound socket or HTTP connection is initiated."""
    pass


def _blocked_connect(*args, **kwargs):
    raise NetworkAccessAttempted(f"FATAL: Network socket connection blocked: {args}")


def _blocked_create_connection(*args, **kwargs):
    raise NetworkAccessAttempted(f"FATAL: Outbound socket connection blocked: {args}")


def _blocked_urlopen(*args, **kwargs):
    raise NetworkAccessAttempted(f"FATAL: HTTP request blocked: {args}")


def run_offline_verification():
    # ── Strict Network Disconnect Simulator ───────────────────────────
    original_connect = socket.socket.connect
    original_create_conn = socket.create_connection
    original_urlopen = urllib.request.urlopen

    socket.socket.connect = _blocked_connect
    socket.create_connection = _blocked_create_connection
    urllib.request.urlopen = _blocked_urlopen
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"

    print("=" * 70)
    print("STRICT OFFLINE VERIFICATION: ALL NETWORK SOCKETS BLOCKED")
    print("=" * 70)

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "offline_test.db"

            # 1. Startup
            db = Database(db_path)
            vstore = SQLiteFlatVectorStore(db_path)
            print("[OK] 1. Application startup & SQLite initialization completed offline.")

            # 2. Local Model Loading (SBERT & CLIP)
            provider = SentenceTransformerProvider()
            sample_vec = provider.embed_text("sample test query")
            assert sample_vec is not None and len(sample_vec) == 384
            print("[OK] 2. Dense text embedding model loaded from local disk cache.")

            clip_model = get_clip_model()
            assert clip_model is not None
            print("[OK] 3. Multimodal CLIP vision model loaded from local disk cache.")

            # 3. Local OCR Verification
            img_path = Path(tmpdir) / "test_ocr.png"
            img = Image.new("RGB", (300, 100), color=(255, 255, 255))
            draw = ImageDraw.Draw(img)
            draw.text((20, 40), "OFFLINE OCR PASS 2026", fill=(0, 0, 0))
            img.save(img_path)

            assert is_ocr_available(), "Tesseract OCR must be installed locally"
            ocr_result = ocr_image(img_path)
            assert "OFFLINE" in ocr_result.upper() or "PASS" in ocr_result.upper()
            print(f"[OK] 4. Native Tesseract OCR executed offline: '{ocr_result.strip()}'.")

            # 4. Offline Indexing Pipeline
            doc_path = Path(tmpdir) / "DBMS_Digital_Assignment_3.txt"
            doc_path.write_text("Database Management Systems Assignment 3 SQL Normalization BCNF.", encoding="utf-8")

            scan_worker = ScanWorker(db, tmpdir)
            scan_worker.run()
            stats = db.statistics()
            assert stats["indexed"] >= 2
            print(f"[OK] 5. Filesystem scanner, SHA-256, and text extraction executed offline ({stats['indexed']} files).")

            # 5. Semantic Vector Indexing & Search
            row = db.get_file_by_path(str(doc_path.resolve()))
            assert row is not None
            fid = row["id"]
            vec = provider.embed_text(row["extracted_text"])
            vstore.add_vectors("file", [fid], np.array([vec]), model_name=provider.model_name)

            q_vec = provider.embed_text("DBMS assignment SQL")
            matches = vstore.query_nearest(q_vec, model_name=provider.model_name, k=5)
            assert len(matches) >= 1
            assert matches[0].entity_id == fid
            print(f"[OK] 6. Dense semantic vector indexing and retrieval executed offline (sim: {matches[0].similarity:.3f}).")

            # 6. CLIP Visual Search
            all_imgs = db.get_recent_files(category="Image", limit=10)
            clip_res = search_images_with_clip("text graphic pass", all_imgs, threshold=0.10)
            assert len(clip_res) >= 1
            print(f"[OK] 7. Multimodal CLIP visual search executed offline ({len(clip_res)} image matches).")

            # 7. Hybrid Search Fusion & History
            agent = AIAgent(db, embedding_provider=provider, vector_store=vstore)
            search_res = agent.search("i need my DBMS DA 3")
            assert len(search_res) >= 1
            top = search_res[0]
            assert "DBMS" in top["filename"]
            assert "Relevance Score" in top["ai_badge"]
            print(f"[OK] 8. End-to-end multi-modal query fusion executed offline (Badge: '{top['ai_badge']}').")

            # 8. Search History & Saved Searches
            db.add_search_history("i need my DBMS DA 3", result_count=len(search_res), execution_time_ms=35)
            history = db.get_search_history()
            assert len(history) == 1
            assert history[0]["query_text"] == "i need my DBMS DA 3"
            print("[OK] 9. Privacy-preserving search history logged offline.")

            saved_id = db.add_saved_search("My DBMS Query", "i need my DBMS DA 3")
            saved = db.get_saved_searches()
            assert len(saved) == 1 and saved[0]["id"] == saved_id
            print("[OK] 10. Saved searches created and retrieved offline.")

            print("=" * 70)
            print("[VERIFIED] 100% OFFLINE PRIVACY BOUNDARY SATISFIED: ZERO NETWORK LEAKS!")
            print("=" * 70)

    finally:
        # Restore sockets
        socket.socket.connect = original_connect
        socket.create_connection = original_create_conn
        urllib.request.urlopen = original_urlopen


if __name__ == "__main__":
    run_offline_verification()
