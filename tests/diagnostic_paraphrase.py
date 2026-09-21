"""
diagnostic_paraphrase.py — Diagnostic Experiment 2: Paraphrase Benchmark
Evaluates full V2 Hybrid Fusion against 25 meaning-preserving queries that
intentionally eliminate exact wording from target filenames.
Tests genuine semantic, FTS body text, and CLIP vision retrieval capabilities.
"""

from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, Any, Optional, List

# Ensure src & tests are in path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from intellifile.database import Database
from intellifile.ai_agent import AIAgent
from intellifile.vector_store import SQLiteFlatVectorStore
from intellifile.embedding_provider import SentenceTransformerProvider
from intellifile.evaluation.benchmark import (
    BenchmarkConditions,
    EvaluationHarness,
    GoldQuery,
    EvaluationReport,
)
from test_ablation import build_ablation_corpus


# 25 Paraphrased Queries designed to test semantic retrieval without lexical filename overlap
PARAPHRASE_BENCHMARK_QUERIES: List[GoldQuery] = [
    GoldQuery("PQ01", "homework assessment covering relational schema normalization and SQL", "academic", ["DBMS_DA_3_Database_Assignment.pdf"], "Document", "Relational DB coursework"),
    GoldQuery("PQ02", "practical coursework on round robin CPU scheduling and threads", "academic", ["Operating_Systems_Lab_2_Process_Scheduling.pdf"], "Document", "OS CPU scheduling lab"),
    GoldQuery("PQ03", "coursework on TCP IP socket programming and packet handshake", "academic", ["Computer_Networks_CN_Assignment.pdf"], "Document", "Networks socket assignment"),
    GoldQuery("PQ04", "gaming team emblem featuring an arachnid", "visual", ["crimson_crawlers_red_spider_logo.png"], "Image", "Esports logo description"),
    GoldQuery("PQ05", "scarlet eight legged arachnid visual badge", "visual", ["crimson_crawlers_red_spider_logo.png"], "Image", "Spider visual description"),
    GoldQuery("PQ06", "visual process map for launching a new venture and customer discovery", "visual", ["startup_flow_diagram_guide.png"], "Image", "Business flowchart"),
    GoldQuery("PQ07", "pair of friends in crimson outfits snapping a phone portrait at a celebration", "visual", ["two_persons_selfie_red_dress.jpg"], "Image", "Celebration photo"),
    GoldQuery("PQ08", "spreadsheet with billing for corporate services and accounts receivable", "lexical", ["quarterly_financial_invoice_q1.xlsx"], "Spreadsheet", "Corporate accounts invoice"),
    GoldQuery("PQ09", "code defining a QRunnable thread pool task with signals", "semantic", ["python_async_search_worker.py"], "Code", "Async worker implementation"),
    GoldQuery("PQ10", "container orchestration file configuring relational storage with volume mounts", "semantic", ["docker_compose_postgres_setup.yaml"], "Code", "Postgres container yaml"),
    GoldQuery("PQ11", "team minutes detailing product roadmap and action items", "lexical", ["meeting_notes_sprint_planning.docx"], "Document", "Team minutes docx"),
    GoldQuery("PQ12", "statistical measures including precision recall and confusion matrix", "semantic", ["machine_learning_model_evaluation_metrics.pdf"], "Document", "ML evaluation metrics"),
    GoldQuery("PQ13", "candidate career profile detailing programming background and education", "lexical", ["software_engineer_curriculum_vitae_resume.pdf"], "Document", "Developer resume"),
    GoldQuery("PQ14", "legal accord governing proprietary secrets and binding covenants", "lexical", ["confidentiality_nda_contract_agreement.pdf"], "Document", "Confidentiality NDA contract"),
    GoldQuery("PQ15", "dusk golden hour horizon overlooking coastal ocean waters", "visual", ["sunset_beach_mountain_landscape.jpg"], "Image", "Coastal horizon photo"),
    GoldQuery("PQ16", "ALTER TABLE script modifying column definitions in sqlite", "semantic", ["sql_database_table_schema_migration.sql"], "Code", "DDL migration script"),
    GoldQuery("PQ17", "preorder and postorder traversal methods for hierarchical binary branches", "academic", ["dsa_tree_traversal_algorithms.pdf"], "Document", "Binary tree traversal"),
    GoldQuery("PQ18", "cinematic film feature with soundtrack in full HD", "hybrid", ["action_movie_video_1080p_bluray.mp4"], "Video", "High definition video"),
    GoldQuery("PQ19", "sound track discussion episode with technical spoken conversation", "hybrid", ["podcast_interview_recording_audio.mp3"], "Audio", "Interview audio track"),
    GoldQuery("PQ20", "compressed tar gz snapshot package for offline storage", "hybrid", ["project_backup_archive_2026.zip"], "Archive", "Compressed archive file"),
    GoldQuery("PQ21", "grocery payment docket showing sales tax amount", "lexical", ["store_receipt_tax_expense_bill.png"], "Image", "Scanned expense receipt"),
    GoldQuery("PQ22", "visual layout for dashboard screen UX prototype", "visual", ["user_interface_design_wireframe_mockup.png"], "Image", "UI mockup layout"),
    GoldQuery("PQ23", "token authorization validation checking header payload secret", "semantic", ["jwt_bearer_token_authentication.py"], "Code", "Token verification logic"),
    GoldQuery("PQ24", "virtual dom UI module managing props and state with JSX", "semantic", ["react_typescript_frontend_component.tsx"], "Code", "Frontend JSX component"),
    GoldQuery("PQ25", "backpropagation optimization theory and gradient descent minimization", "academic", ["deep_neural_network_gradient_loss.pdf"], "Document", "Optimization theory paper"),
]


def run_diagnostic_paraphrase():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "diag_paraphrase.db"
        db = Database(db_path)
        vstore = SQLiteFlatVectorStore(db_path)
        embed_provider = SentenceTransformerProvider()

        total_bytes = build_ablation_corpus(db, tmpdir)

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
            query_count=len(PARAPHRASE_BENCHMARK_QUERIES),
        )

        harness = EvaluationHarness(PARAPHRASE_BENCHMARK_QUERIES)

        print("\n" + "=" * 80)
        print("DIAGNOSTIC EXPERIMENT 2: FULL V2 HYBRID FUSION PARAPHRASE BENCHMARK")
        print("=" * 80)

        report = harness.run_benchmark(
            lambda q, cat: agent.search(q, user_category=cat, limit=10),
            conditions=conditions,
        )

        print(report.summary_table())

        print("\n" + "=" * 125)
        print(f"{'QID':<5} | {'Paraphrased Query':<45} | {'Target File':<35} | {'Rank':<5} | {'Hit@1':<5} | {'RR':<5} | {'nDCG@10':<7}")
        print("-" * 125)
        for r in report.query_results:
            rank_str = str(r.first_relevant_rank) if r.first_relevant_rank is not None else "None"
            print(f"{r.query_id:<5} | {r.query_text[:45]:<45} | {r.target_files[0][:35]:<35} | {rank_str:<5} | {r.hit_1:<5.1f} | {r.reciprocal_rank:<5.3f} | {r.ndcg_10:<7.4f}")
        print("=" * 125)

        return report


if __name__ == "__main__":
    run_diagnostic_paraphrase()
