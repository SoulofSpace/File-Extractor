"""
test_ablation.py — Rigorous V1 vs V2 Ablation Study for FILE XTRACTOR.
Evaluates 6 retrieval variants across all 25 Gold Benchmark Queries:
  Variant A: Filename only
  Variant B: BM25 (Digital text only)
  Variant C: BM25 + OCR
  Variant D: BM25 + OCR + CLIP
  Variant E: BM25 + OCR + CLIP + Semantic Embeddings
  Variant F: Complete V2 Hybrid Fusion
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure src is on Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import tempfile
import time
from typing import Any, Dict, List, Optional
import numpy as np
from PIL import Image

from intellifile.database import Database
from intellifile.ai_agent import AIAgent
from intellifile.vector_store import SQLiteFlatVectorStore
from intellifile.embedding_provider import SentenceTransformerProvider
from intellifile.vision_search import search_images_with_clip
from intellifile.evaluation.benchmark import (
    EvaluationHarness,
    EvaluationReport,
    BenchmarkConditions,
    GOLD_BENCHMARK_QUERIES,
)


def build_ablation_corpus(db: Database, tmpdir: str) -> int:
    """Populates realistic multi-modal test corpus with documents, scans, and images."""
    folder_id = db.add_folder(tmpdir)

    # 25 files matching benchmark scenarios
    corpus_specs = [
        ("DBMS_DA_3_Database_Assignment.pdf", ".pdf", "Document", "Database Management Systems Digital Assignment 3 SQL queries normalization schema.", ""),
        ("Operating_Systems_Lab_2_Process_Scheduling.pdf", ".pdf", "Document", "Operating Systems OS Lab 2 CPU process scheduling round robin multi threading.", ""),
        ("Computer_Networks_CN_Assignment.pdf", ".pdf", "Document", "Computer Networks CN socket programming TCP IP protocol handshake packet inspection.", ""),
        ("crimson_crawlers_red_spider_logo.png", ".png", "Image", "", "Crimson Crawlers esports logo red spider emblem graphic."),
        ("startup_flow_diagram_guide.png", ".png", "Image", "", "Flow diagram for how to start a startup flowchart business model customer discovery."),
        ("two_persons_selfie_red_dress.jpg", ".jpg", "Image", "", "Two people persons taking selfie wearing red dress party photo vacation."),
        ("quarterly_financial_invoice_q1.xlsx", ".xlsx", "Spreadsheet", "Quarterly financial invoice bill billing payment services tax accounts receivable.", ""),
        ("python_async_search_worker.py", ".py", "Code", "class SearchWorker QRunnable async search script py thread pool signals.", ""),
        ("docker_compose_postgres_setup.yaml", ".yaml", "Code", "services postgres database setup docker compose yaml sql ports volumes.", ""),
        ("meeting_notes_sprint_planning.docx", ".docx", "Document", "Team meeting notes sprint planning sprint backlog roadmap minutes action items.", ""),
        ("machine_learning_model_evaluation_metrics.pdf", ".pdf", "Document", "Machine learning ML model evaluation metrics precision recall f1 ndcg confusion matrix.", ""),
        ("software_engineer_curriculum_vitae_resume.pdf", ".pdf", "Document", "Curriculum vitae resume software engineer python developer profile experience education.", ""),
        ("confidentiality_nda_contract_agreement.pdf", ".pdf", "Document", "Non disclosure confidentiality NDA contract legal agreement binding covenants.", ""),
        ("sunset_beach_mountain_landscape.jpg", ".jpg", "Image", "", "Sunset landscape beach ocean mountain sky nature scenic photo horizon."),
        ("sql_database_table_schema_migration.sql", ".sql", "Code", "ALTER TABLE files ADD COLUMN database table schema migration sql sqlite.", ""),
        ("dsa_tree_traversal_algorithms.pdf", ".pdf", "Document", "Data Structures Algorithms DSA binary search tree traversal preorder inorder postorder.", ""),
        ("action_movie_video_1080p_bluray.mp4", ".mp4", "Video", "Action movie video 1080p high definition media film soundtrack feature.", ""),
        ("podcast_interview_recording_audio.mp3", ".mp3", "Audio", "Tech podcast interview audio recording episode sound file discussion conversation.", ""),
        ("project_backup_archive_2026.zip", ".zip", "Archive", "Compressed archive backup zip file storage tar gz files.", ""),
        ("store_receipt_tax_expense_bill.png", ".png", "Image", "", "Receipt tax deduction expense grocery store payment invoice ocr amount."),
        ("user_interface_design_wireframe_mockup.png", ".png", "Image", "", "UI UX design mockup wireframe interface user dashboard art layout."),
        ("jwt_bearer_token_authentication.py", ".py", "Code", "JWT authentication bearer token authorization verify header py payload secret.", ""),
        ("react_typescript_frontend_component.tsx", ".tsx", "Code", "React TypeScript frontend component tsx props state interface jsx virtual dom.", ""),
        ("deep_neural_network_gradient_loss.pdf", ".pdf", "Document", "Deep neural network loss function gradient descent backpropagation theory optimization.", ""),
        ("scratch_unrelated_random_file.txt", ".txt", "Document", "Completely unrelated miscellaneous test file negative baseline item.", ""),
    ]

    total_bytes = 0
    with db.connection() as conn:
        for fname, ext, cat, text_native, text_ocr in corpus_specs:
            fpath = str(Path(tmpdir) / fname)
            file_bytes = 1024
            total_bytes += file_bytes

            if ext in (".png", ".jpg"):
                img = Image.new("RGB", (64, 64), color=(80, 80, 80))
                img.save(fpath)

            conn.execute(
                """
                INSERT INTO files (
                    folder_id, filename, path, extension, file_type, size_bytes,
                    created_at, modified_at, indexed_at, indexing_status,
                    extracted_text, ocr_text
                ) VALUES (?, ?, ?, ?, ?, ?, 1.0, 1.0, 'now', 'indexed', ?, ?)
                """,
                (folder_id, fname, fpath, ext, cat, file_bytes, text_native, text_ocr),
            )
            fid = conn.execute("SELECT id FROM files WHERE path = ?", (fpath,)).fetchone()[0]

            # Populate FTS5 with digital text and OCR text
            combined = (text_native + "\n" + text_ocr).strip()
            conn.execute(
                "INSERT INTO file_search (file_id, filename, content) VALUES (?, ?, ?)",
                (str(fid), fname, f"{fname}\n{combined}"),
            )

    return total_bytes


def run_ablation_study():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "ablation.db"
        db = Database(db_path)
        vstore = SQLiteFlatVectorStore(db_path)
        embed_provider = SentenceTransformerProvider()

        total_bytes = build_ablation_corpus(db, tmpdir)

        # Pre-populate embeddings for semantic search
        all_files = db.get_recent_files(limit=50)
        file_ids = [int(f["id"]) for f in all_files]
        file_texts = [f"{f['filename']} {f.get('extracted_text','')}" for f in all_files]
        vectors = embed_provider.embed_batch(file_texts)
        vstore.add_vectors("file", file_ids, vectors, model_name=embed_provider.model_name)

        agent_v2 = AIAgent(db, embedding_provider=embed_provider, vector_store=vstore)

        conditions = BenchmarkConditions(
            corpus_size_bytes=total_bytes,
            num_indexed_files=len(all_files),
            num_text_chunks=len(all_files),
            num_image_embeddings=sum(1 for f in all_files if f.get("extension") in (".png", ".jpg")),
            cold_warm_state="warm",
            query_count=25,
        )

        harness = EvaluationHarness(GOLD_BENCHMARK_QUERIES)

        # ── Variant A: Filename only ──────────────────────────────────
        def search_variant_a(query: str, category: Optional[str] = None) -> list[dict]:
            clean = "".join(c if c.isalnum() else " " for c in query.lower())
            tokens = [t for t in clean.split() if len(t) > 1]
            if not tokens:
                return []
            with db.connection() as conn:
                where_clauses = " OR ".join("LOWER(filename) LIKE ?" for _ in tokens)
                params = [f"%{t}%" for t in tokens]
                sql = f"SELECT * FROM files WHERE {where_clauses} LIMIT 20"
                rows = conn.execute(sql, params).fetchall()
                return [dict(r) for r in rows]

        # ── Variant B: BM25 (Digital text only) ────────────────────────
        def search_variant_b(query: str, category: Optional[str] = None) -> list[dict]:
            clean = "".join(c if c.isalnum() else " " for c in query.lower())
            tokens = [t for t in clean.split() if len(t) > 1]
            if not tokens:
                return []
            with db.connection() as conn:
                where_clauses = " OR ".join("LOWER(extracted_text) LIKE ? OR LOWER(filename) LIKE ?" for _ in tokens)
                params = []
                for t in tokens:
                    params.extend([f"%{t}%", f"%{t}%"])
                sql = f"SELECT * FROM files WHERE {where_clauses} LIMIT 20"
                rows = conn.execute(sql, params).fetchall()
                return [dict(r) for r in rows]

        # ── Variant C: BM25 + OCR ─────────────────────────────────────
        def search_variant_c(query: str, category: Optional[str] = None) -> list[dict]:
            return db.keyword_search(query, category=category, limit=20)

        # ── Variant D: BM25 + OCR + CLIP ──────────────────────────────
        def search_variant_d(query: str, category: Optional[str] = None) -> list[dict]:
            fts_hits = db.keyword_search(query, category=category, limit=20)
            images = db.get_recent_files(category="Image", limit=50)
            clip_hits = search_images_with_clip(query, images, limit=10) if images else []
            combined = clip_hits + fts_hits
            seen = set()
            out = []
            for item in combined:
                p = item.get("path")
                if p not in seen:
                    seen.add(p)
                    out.append(item)
            return out[:20]

        # ── Variant E: BM25 + OCR + CLIP + Semantic Embeddings ─────────
        def search_variant_e(query: str, category: Optional[str] = None) -> list[dict]:
            d_hits = search_variant_d(query, category)
            q_vec = embed_provider.embed_text(query)
            vec_matches = vstore.query_nearest(q_vec, model_name=embed_provider.model_name, k=10)
            seen = {h.get("path") for h in d_hits}
            for vm in vec_matches:
                rec = db.get_file_by_id(vm.entity_id)
                if rec and rec.get("path") not in seen:
                    seen.add(rec.get("path"))
                    d_hits.append(rec)
            return d_hits[:20]

        # ── Variant F: Complete V2 Hybrid Fusion ───────────────────────
        def search_variant_f(query: str, category: Optional[str] = None) -> list[dict]:
            return agent_v2.search(query, user_category=category, limit=20)

        variants = [
            ("Variant A: Filename only", search_variant_a),
            ("Variant B: BM25 (Digital text only)", search_variant_b),
            ("Variant C: BM25 + OCR", search_variant_c),
            ("Variant D: BM25 + OCR + CLIP", search_variant_d),
            ("Variant E: BM25 + OCR + CLIP + SBERT", search_variant_e),
            ("Variant F: Complete V2 Hybrid Fusion", search_variant_f),
        ]

        reports: Dict[str, EvaluationReport] = {}

        print("\n" + "=" * 80)
        print("RUNNING V1 VS V2 COMPREHENSIVE ABLATION STUDY (25 GOLD BENCHMARK QUERIES)")
        print("=" * 80)

        for name, search_fn in variants:
            t0 = time.time()
            rep = harness.run_benchmark(search_fn, conditions=conditions)
            reports[name] = rep
            print(f"Completed {name} in {time.time()-t0:.2f}s -> Hit@1: {rep.hit_1:.4f}, Hit@10: {rep.hit_10:.4f}, MRR: {rep.mrr:.4f}, P50: {rep.p50_latency_ms:.1f}ms")

        # Print Comparative Table
        print("\n" + "=" * 105)
        print("V1 VS V2 COMPONENT ABLATION MATRIX (EVALUATION ACROSS 25 GOLD QUERIES)")
        print("=" * 105)
        header = f"{'Retrieval Variant':<36} | {'Hit@1':<7} | {'Hit@3':<7} | {'Hit@5':<7} | {'Hit@10':<7} | {'MRR':<7} | {'nDCG@10':<7} | {'P50 (ms)':<8}"
        print(header)
        print("-" * 105)

        for name, r in reports.items():
            line = f"{name:<36} | {r.hit_1:<7.4f} | {r.hit_3:<7.4f} | {r.hit_5:<7.4f} | {r.hit_10:<7.4f} | {r.mrr:<7.4f} | {r.mean_ndcg10:<7.4f} | {r.p50_latency_ms:<8.2f}"
            print(line)
        print("=" * 105)

        return reports


if __name__ == "__main__":
    run_ablation_study()
