"""
test_evaluation_benchmark.py — Executes the 25 Gold Benchmark Queries on FILE XTRACTOR V2.
Evaluates the full V2 Hybrid Architecture:
  Lexical FTS5 + Acronym Expansion + Dense SBERT Vectors + Multimodal CLIP Vision.
Computes mathematically verified IR metrics:
  Hit@1, Hit@3, Hit@5, Hit@10, Precision@5, Precision@10, Recall@10, MRR, nDCG@10, Latencies.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure src is on Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import tempfile
from PIL import Image

from intellifile.database import Database
from intellifile.ai_agent import AIAgent
from intellifile.vector_store import SQLiteFlatVectorStore
from intellifile.embedding_provider import SentenceTransformerProvider
from intellifile.evaluation.benchmark import (
    BenchmarkConditions,
    EvaluationHarness,
    GOLD_BENCHMARK_QUERIES,
)
from test_ablation import build_ablation_corpus


def run_gold_benchmark():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "benchmark.db"
        db = Database(db_path)
        vstore = SQLiteFlatVectorStore(db_path)
        embed_provider = SentenceTransformerProvider()

        # Build full multi-modal corpus (documents, code, spreadsheets, media, images)
        total_bytes = build_ablation_corpus(db, tmpdir)

        # Precompute dense vectors for semantic text retrieval
        all_files = db.get_recent_files(limit=50)
        file_ids = [int(f["id"]) for f in all_files]
        file_texts = [f"{f['filename']} {f.get('extracted_text','')}" for f in all_files]
        vectors = embed_provider.embed_batch(file_texts)
        vstore.add_vectors("file", file_ids, vectors, model_name=embed_provider.model_name)

        # Complete V2 Multi-Modal Agent
        agent = AIAgent(db, embedding_provider=embed_provider, vector_store=vstore)

        conditions = BenchmarkConditions(
            corpus_size_bytes=total_bytes,
            num_indexed_files=len(all_files),
            num_text_chunks=len(all_files),
            num_image_embeddings=sum(1 for f in all_files if f.get("extension") in (".png", ".jpg")),
            cold_warm_state="warm",
            query_count=len(GOLD_BENCHMARK_QUERIES),
        )

        harness = EvaluationHarness(GOLD_BENCHMARK_QUERIES)

        print(f"Executing Evaluation Harness across {len(GOLD_BENCHMARK_QUERIES)} gold queries...")
        report = harness.run_benchmark(
            lambda q, cat: agent.search(q, user_category=cat, limit=10),
            conditions=conditions,
        )

        print("\n" + report.summary_table())

        # Assertions on IR quality for known-item / navigational benchmark queries
        assert report.total_queries == 25, f"Expected 25 queries, got {report.total_queries}"
        assert report.hit_1 >= 0.90, f"Hit@1 {report.hit_1:.4f} below threshold 0.90"
        assert report.hit_5 >= 0.95, f"Hit@5 {report.hit_5:.4f} below threshold 0.95"
        assert report.hit_10 == 1.00, f"Hit@10 {report.hit_10:.4f} below threshold 1.00"
        assert report.mrr >= 0.90, f"Mean Reciprocal Rank {report.mrr:.4f} below threshold 0.90"
        assert report.mean_recall10 == 1.00, f"Mean Recall@10 {report.mean_recall10:.4f} below threshold 1.00"
        assert 0.0 <= report.mean_ndcg10 <= 1.0, f"Mean nDCG@10 {report.mean_ndcg10:.4f} out of valid [0.0, 1.0] bounds"
        assert report.mean_ndcg10 >= 0.95, f"Mean nDCG@10 {report.mean_ndcg10:.4f} below threshold 0.95"
        assert report.p50_latency_ms < 100.0, f"P50 Latency {report.p50_latency_ms:.2f}ms above threshold 100ms"
        assert report.p95_latency_ms < 200.0, f"P95 Latency {report.p95_latency_ms:.2f}ms above threshold 200ms"

        print("\n[SUCCESS] ALL EVALUATION HARNESS THRESHOLDS SATISFIED WITH MATHEMATICAL INTEGRITY!")
        return report


if __name__ == "__main__":
    run_gold_benchmark()
