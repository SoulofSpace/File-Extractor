"""
test_v2_architecture.py — Verification test suite for Sprint 0 architecture contracts.
Tests hashing, perceptual hashing, SQLiteFlatVectorStore, Database V2 schema, and EvaluationHarness.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure src is on Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import tempfile
import numpy as np
from PIL import Image

from intellifile.domain.hashing import fast_mtime_size_check, compute_sha256, get_file_identity
from intellifile.domain.phash import compute_phash, hamming_distance
from intellifile.vector_store import SQLiteFlatVectorStore
from intellifile.embedding_provider import SentenceTransformerProvider
from intellifile.database import Database
from intellifile.evaluation.benchmark import (
    EvaluationHarness,
    GoldQuery,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
    ndcg_at_k,
)


def test_hashing_and_fast_path():
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tf:
        tf.write(b"FILE XTRACTOR V2 cryptographic hash test\n")
        tf_path = Path(tf.name)

    try:
        identity = get_file_identity(tf_path)
        assert identity is not None
        assert identity.sha256_hash is not None
        assert len(identity.sha256_hash) == 64

        # Fast path check should succeed
        assert fast_mtime_size_check(tf_path, identity.size_bytes, identity.modified_at)
        # Modified size should fail
        assert not fast_mtime_size_check(tf_path, identity.size_bytes + 10, identity.modified_at)
    finally:
        tf_path.unlink(missing_ok=True)


def test_perceptual_hash():
    with tempfile.TemporaryDirectory() as tmpdir:
        img1_path = Path(tmpdir) / "test1.png"
        img2_path = Path(tmpdir) / "test2.png"

        # Create two images with identical structure (a white square on dark background)
        img1 = Image.new("RGB", (100, 100), color=(20, 20, 20))
        for x in range(30, 70):
            for y in range(30, 70):
                img1.putpixel((x, y), (240, 240, 240))
        img1.save(img1_path)

        # Image 2 is the same with tiny noise (+5 pixel values)
        img2 = Image.new("RGB", (100, 100), color=(25, 25, 25))
        for x in range(30, 70):
            for y in range(30, 70):
                img2.putpixel((x, y), (245, 245, 245))
        img2.save(img2_path)

        h1 = compute_phash(img1_path)
        h2 = compute_phash(img2_path)

        assert h1 is not None and len(h1) == 16
        assert h2 is not None and len(h2) == 16
        # Almost identical red squares should have very low Hamming distance
        dist = hamming_distance(h1, h2)
        assert dist <= 5


def test_vector_store():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_vectors.db"
        vstore = SQLiteFlatVectorStore(db_path)

        # Insert 3 test vectors of dimension 4
        # v1: pointing in x direction [1, 0, 0, 0]
        # v2: pointing close to x direction [0.9, 0.1, 0, 0]
        # v3: pointing in orthogonal y direction [0, 1, 0, 0]
        vectors = np.array([
            [1.0, 0.0, 0.0, 0.0],
            [0.9, 0.1, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0],
        ], dtype=np.float32)

        vstore.add_vectors(
            entity_type="file",
            entity_ids=[101, 102, 103],
            vectors=vectors,
            model_name="test-model",
            model_version="1.0",
        )

        # Query with [1, 0, 0, 0]
        matches = vstore.query_nearest(
            query_vector=np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32),
            model_name="test-model",
            k=2,
        )

        assert len(matches) == 2
        # First match should be 101 with ~1.0 similarity
        assert matches[0].entity_id == 101
        assert abs(matches[0].similarity - 1.0) < 1e-4
        # Second match should be 102
        assert matches[1].entity_id == 102

        # Test deletion
        vstore.delete_vectors(entity_type="file", entity_ids=[101])
        remaining = vstore.query_nearest(
            query_vector=np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32),
            model_name="test-model",
            k=2,
        )
        assert len(remaining) == 2
        assert remaining[0].entity_id == 102


def test_database_v2_migration():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_migration.db"
        db = Database(db_path)

        # Verify PRAGMA user_version is at least 2
        with db.connection() as conn:
            ver = conn.execute("PRAGMA user_version").fetchone()[0]
            assert ver >= 2

        # Verify search history methods
        db.add_search_history("query 1", result_count=5, execution_time_ms=12)
        history = db.get_search_history()
        assert len(history) == 1
        assert history[0]["query_text"] == "query 1"
        assert history[0]["result_count"] == 5

        # Verify saved search
        sid = db.add_saved_search("My Saved Search", "DBMS assignment", '{"target_cat": "Document"}')
        assert sid > 0
        saved = db.get_saved_searches()
        assert len(saved) == 1
        assert saved[0]["name"] == "My Saved Search"

        # Verify page storage
        folder_id = db.add_folder(Path(tmpdir) / "test_folder")
        # Upsert a dummy file
        with db.connection() as conn:
            conn.execute(
                """
                INSERT INTO files (folder_id, filename, path, extension, file_type, size_bytes, created_at, modified_at, indexed_at, indexing_status)
                VALUES (?, 'doc.pdf', 'C:/test/doc.pdf', '.pdf', 'Document', 1000, 1.0, 1.0, 'now', 'indexed')
                """,
                (folder_id,)
            )
            file_id = conn.execute("SELECT id FROM files WHERE path = 'C:/test/doc.pdf'").fetchone()[0]

        db.store_page_content(file_id=file_id, page_number=1, chunk_index=0, text="Introduction to database management systems.")
        pages = db.get_pages_for_file(file_id)
        assert len(pages) == 1
        assert "database" in pages[0]["text"]

        # Verify index jobs
        db.upsert_index_job(folder_id, "C:/test/doc.pdf", stage="extracted", status="completed")
        jobs = db.get_pending_index_jobs()
        assert len(jobs) == 0  # Since it is 'completed'


def test_evaluation_harness_metrics():
    retrieved = ["path/to/DBMS_DA3.pdf", "path/to/notes.txt", "path/to/image.png"]
    expected = ["DBMS_DA3.pdf"]

    # In standard IR, Precision@k has denominator k=5 (not len(retrieved))
    p5 = precision_at_k(retrieved, expected, k=5)
    assert abs(p5 - (1.0 / 5.0)) < 1e-4

    r10 = recall_at_k(retrieved, expected, k=10)
    assert r10 == 1.0

    rr = reciprocal_rank(retrieved, expected)
    assert rr == 1.0  # First item matches

    ndcg = ndcg_at_k(retrieved, expected, k=10)
    assert ndcg == 1.0

    # Test dummy evaluation run
    dummy_query = GoldQuery("QTEST", "test query", "lexical", ["DBMS_DA3.pdf"])
    harness = EvaluationHarness(queries=[dummy_query])

    def mock_search(q: str, cat: str | None = None):
        return [{"path": "C:/files/DBMS_DA3.pdf"}]

    report = harness.run_benchmark(mock_search)
    assert report.total_queries == 1
    assert abs(report.mean_p5 - 0.20) < 1e-4
    assert report.mrr == 1.0
    assert report.p50_latency_ms >= 0.0


def test_embedding_provider_contract():
    provider = SentenceTransformerProvider(model_name="all-MiniLM-L6-v2")
    assert provider.model_name == "all-MiniLM-L6-v2"
    assert provider.model_version == "2.0.0"
    assert provider.normalization_method == "l2"
    assert provider.preprocessing_version == "sbert-standard-v1"


if __name__ == "__main__":
    print("Running Sprint 0 architecture test suite...")
    test_hashing_and_fast_path()
    print("[OK] Hashing and fast-path tests passed.")
    test_perceptual_hash()
    print("[OK] Perceptual hash tests passed.")
    test_vector_store()
    print("[OK] SQLiteFlatVectorStore tests passed.")
    test_database_v2_migration()
    print("[OK] Database V2 migration tests passed.")
    test_evaluation_harness_metrics()
    print("[OK] Evaluation harness metrics tests passed.")
    test_embedding_provider_contract()
    print("[OK] Embedding provider contract tests passed.")
    print("ALL SPRINT 0 ARCHITECTURE TESTS PASSED SUCCESSFULLY!")
