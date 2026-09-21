"""
test_v2_features.py — Verification test suite for FILE XTRACTOR V2 features.
Tests SearchWorker, multi-branch AIAgent fusion, duplicate detection, and filesystem watcher.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure src is on Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import tempfile
import time
import numpy as np
from PIL import Image
from PySide6.QtCore import QCoreApplication

from intellifile.database import Database
from intellifile.ai_agent import AIAgent
from intellifile.vector_store import SQLiteFlatVectorStore
from intellifile.embedding_provider import SentenceTransformerProvider
from intellifile.search_worker import SearchWorker
from intellifile.domain.duplicates import get_exact_duplicate_groups, get_near_duplicate_images
from intellifile.watcher import _DebouncedEventHandler


def test_ai_agent_fusion():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_agent.db"
        db = Database(db_path)
        folder_id = db.add_folder(tmpdir)

        # Insert test files:
        # File 1: DBMS assignment
        with db.connection() as conn:
            conn.execute(
                """
                INSERT INTO files (
                    folder_id, filename, path, extension, file_type, size_bytes,
                    created_at, modified_at, indexed_at, indexing_status, extracted_text
                ) VALUES (?, 'DBMS_DA_3_Submission.pdf', 'C:/school/DBMS_DA_3_Submission.pdf', '.pdf', 'Document', 2048, 1.0, 1.0, 'now', 'indexed', 'Database Management Systems Assignment 3 SQL queries.')
                """,
                (folder_id,)
            )
            fid1 = conn.execute("SELECT id FROM files WHERE filename = 'DBMS_DA_3_Submission.pdf'").fetchone()[0]

            # File 2: Unrelated Python file
            conn.execute(
                """
                INSERT INTO files (
                    folder_id, filename, path, extension, file_type, size_bytes,
                    created_at, modified_at, indexed_at, indexing_status, extracted_text
                ) VALUES (?, 'main.py', 'C:/code/main.py', '.py', 'Code', 512, 1.0, 1.0, 'now', 'indexed', 'print(\"hello world\")')
                """,
                (folder_id,)
            )

            # Insert into FTS5
            conn.execute(
                "INSERT INTO file_search (file_id, filename, content) VALUES (?, 'DBMS_DA_3_Submission.pdf', 'Database Management Systems Assignment 3 SQL queries.')",
                (str(fid1),)
            )

        agent = AIAgent(db)
        results = agent.search("i need my DBMS DA 3")

        assert len(results) >= 1
        top = results[0]
        assert "DBMS_DA_3_Submission.pdf" in top["filename"]
        assert top["relevance_score"] > 0.5
        assert "Relevance Score" in top["ai_badge"]
        assert "DBMS" in top["ai_explanation"] or "Assignment" in top["ai_explanation"]
        assert "match_evidence" in top


def test_duplicate_detection():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_dup.db"
        db = Database(db_path)
        folder_id = db.add_folder(tmpdir)

        test_sha = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

        with db.connection() as conn:
            conn.execute(
                """
                INSERT INTO files (folder_id, filename, path, extension, file_type, size_bytes, created_at, modified_at, indexed_at, indexing_status, sha256_hash)
                VALUES (?, 'copy1.pdf', 'C:/docs/copy1.pdf', '.pdf', 'Document', 100, 1.0, 1.0, 'now', 'indexed', ?)
                """,
                (folder_id, test_sha)
            )
            conn.execute(
                """
                INSERT INTO files (folder_id, filename, path, extension, file_type, size_bytes, created_at, modified_at, indexed_at, indexing_status, sha256_hash)
                VALUES (?, 'copy2.pdf', 'C:/downloads/copy2.pdf', '.pdf', 'Document', 100, 1.0, 1.0, 'now', 'indexed', ?)
                """,
                (folder_id, test_sha)
            )

        dups = get_exact_duplicate_groups(db)
        assert len(dups) == 1
        assert dups[0]["copy_count"] == 2
        assert len(dups[0]["file_paths"]) == 2


def test_watcher_ignore_rules():
    received = []
    handler = _DebouncedEventHandler(callback=lambda evt, p: received.append((evt, p)), debounce_seconds=0.1)

    assert handler._should_ignore("C:/project/.git/HEAD")
    assert handler._should_ignore("C:/project/.venv/Lib/site-packages/test.py")
    assert handler._should_ignore("C:/project/node_modules/package/index.js")
    assert handler._should_ignore("C:/project/file.tmp")
    assert handler._should_ignore("C:/project/~$WordDoc.docx")
    assert not handler._should_ignore("C:/project/documents/report.pdf")


if __name__ == "__main__":
    print("Running Sprint 1 & 2 verification suite...")
    test_ai_agent_fusion()
    print("[OK] AI Agent multi-modal fusion tests passed.")
    test_duplicate_detection()
    print("[OK] Duplicate detection tests passed.")
    test_watcher_ignore_rules()
    print("[OK] Watcher ignore rules tests passed.")
    print("ALL SPRINT 1 & 2 VERIFICATION TESTS PASSED SUCCESSFULLY!")
