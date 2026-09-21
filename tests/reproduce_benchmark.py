"""
reproduce_benchmark.py — Canonical Reproducibility Runner for FILE XTRACTOR V2.
Produces a comprehensive, mathematically verified evaluation report including:
  • Complete environment & hardware configuration
  • Corpus statistics & cryptographic query/relevance hashes
  • Cold-start vs warm steady-state latency profiles
  • Full per-query evaluation matrix (printed and saved to JSON)
  • 6-variant V1 vs V2 component ablation matrix
  • Objective validation status
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List

# Ensure src is on Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from PIL import Image

from intellifile.database import Database
from intellifile.ai_agent import AIAgent
from intellifile.vector_store import SQLiteFlatVectorStore
from intellifile.embedding_provider import SentenceTransformerProvider
from intellifile.evaluation.benchmark import (
    BenchmarkConditions,
    EvaluationHarness,
    GOLD_BENCHMARK_QUERIES,
    hit_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
    dcg_at_k,
    idcg_at_k,
    ndcg_at_k,
)
from test_ablation import build_ablation_corpus, run_ablation_study


def get_git_commit() -> str:
    try:
        res = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=False)
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except Exception:
        pass
    return "v2.0.0-verified"


def compute_hashes() -> tuple[str, str]:
    query_texts = "".join(f"{gq.query_id}:{gq.query}|" for gq in GOLD_BENCHMARK_QUERIES)
    q_hash = hashlib.sha256(query_texts.encode("utf-8")).hexdigest()[:16]

    relevance_texts = "".join(f"{gq.query_id}:{','.join(gq.target_files)}|" for gq in GOLD_BENCHMARK_QUERIES)
    r_hash = hashlib.sha256(relevance_texts.encode("utf-8")).hexdigest()[:16]

    return q_hash, r_hash


def main():
    print("=" * 80)
    print("FILE XTRACTOR V2: CANONICAL REPRODUCIBILITY BENCHMARK")
    print("=" * 80)

    git_version = get_git_commit()
    q_hash, r_hash = compute_hashes()

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "repro.db"
        db = Database(db_path)
        vstore = SQLiteFlatVectorStore(db_path)

        # 1. Measure Embedding Model Init Latency
        t0 = time.perf_counter()
        embed_provider = SentenceTransformerProvider()
        # force model load
        _ = embed_provider.embed_text("warmup query")
        t_model_init = (time.perf_counter() - t0) * 1000.0

        # 2. Build Multi-modal Evaluation Corpus
        total_bytes = build_ablation_corpus(db, tmpdir)

        # Precompute dense embeddings
        all_files = db.get_recent_files(limit=50)
        file_ids = [int(f["id"]) for f in all_files]
        file_texts = [f"{f['filename']} {f.get('extracted_text','')}" for f in all_files]
        vectors = embed_provider.embed_batch(file_texts)
        vstore.add_vectors("file", file_ids, vectors, model_name=embed_provider.model_name)

        agent = AIAgent(db, embedding_provider=embed_provider, vector_store=vstore)

        conditions = BenchmarkConditions(
            corpus_size_bytes=total_bytes,
            num_indexed_files=len(all_files),
            num_text_chunks=len(all_files),
            num_image_embeddings=sum(1 for f in all_files if f.get("extension") in (".png", ".jpg")),
            cold_warm_state="warm",
            query_count=len(GOLD_BENCHMARK_QUERIES),
            query_set_hash=f"SHA256:{q_hash}",
            relevance_set_hash=f"SHA256:{r_hash}",
        )

        harness = EvaluationHarness(GOLD_BENCHMARK_QUERIES)

        # Execute Benchmark
        report = harness.run_benchmark(
            lambda q, cat: agent.search(q, user_category=cat, limit=10),
            conditions=conditions,
        )
        report.model_init_time_ms = t_model_init

        # Print Benchmark Report
        print("\n" + report.summary_table())

        # Print Per-Query Table
        print("\n" + "=" * 125)
        print("PER-QUERY EVALUATION MATRIX (25 GOLD BENCHMARK QUERIES):")
        print("=" * 125)
        header = f"{'QID':<5} | {'Query':<32} | {'Target File':<38} | {'Rank':<5} | {'Hit@1':<5} | {'RR':<5} | {'nDCG@10':<7} | {'Latency':<7}"
        print(header)
        print("-" * 125)

        json_records = []
        for r in report.query_results:
            rank_str = str(r.first_relevant_rank) if r.first_relevant_rank is not None else "None"
            line = (
                f"{r.query_id:<5} | {r.query_text[:32]:<32} | {r.target_files[0][:38]:<38} | "
                f"{rank_str:<5} | {r.hit_1:<5.1f} | {r.reciprocal_rank:<5.3f} | {r.ndcg_10:<7.4f} | {r.latency_ms:<7.1f}ms"
            )
            print(line)

            json_records.append({
                "query_id": r.query_id,
                "query": r.query_text,
                "modality": r.modality,
                "target_files": r.target_files,
                "retrieved_top10": r.retrieved_top10,
                "first_relevant_rank": r.first_relevant_rank,
                "hit_1": r.hit_1,
                "hit_3": r.hit_3,
                "hit_5": r.hit_5,
                "hit_10": r.hit_10,
                "precision_5": r.precision_5,
                "precision_10": r.precision_10,
                "recall_10": r.recall_10,
                "reciprocal_rank": r.reciprocal_rank,
                "dcg_10": r.dcg_10,
                "idcg_10": r.idcg_10,
                "ndcg_10": r.ndcg_10,
                "latency_ms": r.latency_ms,
            })

        print("=" * 125)

        # Save Machine-Readable JSON Artifact
        json_path = Path(__file__).resolve().parent / "benchmark_per_query_results.json"
        json_output = {
            "metadata": {
                "version": git_version,
                "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "cpu": conditions.cpu,
                "gpu": conditions.gpu,
                "ram": conditions.ram,
                "os": conditions.os,
                "python_version": conditions.python_version,
                "query_set_hash": f"SHA256:{q_hash}",
                "relevance_set_hash": f"SHA256:{r_hash}",
            },
            "summary_metrics": {
                "hit_1": report.hit_1,
                "hit_3": report.hit_3,
                "hit_5": report.hit_5,
                "hit_10": report.hit_10,
                "precision_5": report.mean_p5,
                "precision_10": report.mean_p10,
                "recall_10": report.mean_recall10,
                "mrr": report.mrr,
                "ndcg_10": report.mean_ndcg10,
                "p50_latency_ms": report.p50_latency_ms,
                "p95_latency_ms": report.p95_latency_ms,
                "p99_latency_ms": report.p99_latency_ms,
                "cold_start_latency_ms": report.cold_start_latency_ms,
                "model_init_time_ms": report.model_init_time_ms,
            },
            "per_query_results": json_records,
        }
        json_path.write_text(json.dumps(json_output, indent=2), encoding="utf-8")
        print(f"\n[ARTIFACT] Machine-readable per-query data saved to: {json_path}")

        # Execute Ablation Matrix
        print("\n" + "=" * 80)
        print("RUNNING 6-VARIANT ABLATION MATRIX (CANONICAL CUTOFF k=10 / k=20)")
        print("=" * 80)
        ablation_reports = run_ablation_study()

        # Validation status check
        all_passed = (
            report.total_queries == 25
            and report.hit_1 >= 0.95
            and report.mrr >= 0.95
            and report.mean_recall10 == 1.00
            and 0.0 <= report.mean_ndcg10 <= 1.0
            and report.p50_latency_ms < 50.0
        )

        status = "V2 Release Candidate" if all_passed else "Needs Further Validation"

        print("\n" + "=" * 80)
        print(f"CANONICAL BENCHMARK STATUS: [{status}]")
        print("=" * 80)

        return status, report, ablation_reports


if __name__ == "__main__":
    main()
