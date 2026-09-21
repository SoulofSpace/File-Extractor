"""
diagnostic_no_filename.py — Diagnostic Experiment 1: Ablation Without Filename Matching
Measures genuine semantic/multimodal retrieval effectiveness by eliminating Branch 4 filename matching.
Evaluates BM25 (text & OCR) + Dense SBERT + Multimodal CLIP Vision + Metadata filtering.
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
    GOLD_BENCHMARK_QUERIES,
    EvaluationReport,
)
from test_ablation import build_ablation_corpus


class NoFilenameAgent(AIAgent):
    """
    Subclass of AIAgent that zeroes out the filename match bonus (Branch 4)
    and re-normalizes fusion weights across CLIP, BM25, and SBERT.
    """

    def search(
        self,
        query: str,
        user_category: Optional[str] = None,
        limit: int = 45,
    ) -> list[dict]:
        plan = self.parse_query(query)

        candidates: Dict[str, Dict[str, Any]] = {}

        def get_or_create(path_str: str, file_dict: dict) -> Dict[str, Any]:
            if path_str not in candidates:
                candidates[path_str] = {
                    "record": dict(file_dict),
                    "file_score": 0.0,
                    "bm25_score": 0.0,
                    "sem_score": 0.0,
                    "clip_score": 0.0,
                    "reasons": [],
                    "snippet": file_dict.get("snippet", ""),
                }
            return candidates[path_str]

        # ── Branch 1: Deep Multimodal CLIP Vision Search ──────────────
        from intellifile.vision_search import search_images_with_clip

        if user_category:
            should_clip = (user_category.strip().upper() == "IMAGE")
        else:
            should_clip = plan.is_visual
        if should_clip:
            all_images = self.database.get_recent_files(category="Image", limit=150)
            if all_images:
                clip_hits = search_images_with_clip(
                    plan.cleaned_query,
                    all_images,
                    threshold=0.19,
                    limit=20,
                )
                for hit in clip_hits:
                    p_str = str(hit.get("path", ""))
                    if not p_str:
                        continue
                    entry = get_or_create(p_str, hit)
                    raw_sim = float(hit.get("rank", 0.0))
                    if raw_sim < 0:
                        raw_sim = -raw_sim
                    sim_norm = min(1.0, max(0.0, (raw_sim - 0.18) / 0.16))
                    entry["clip_score"] = sim_norm
                    entry["reasons"].append(f"Visual CLIP match ({sim_norm:.2f})")

        # ── Branch 2: Lexical Full-Text Search (SQLite FTS5 BM25) ─────
        fts_cat = user_category or plan.target_category
        fts_hits = self.database.keyword_search(
            plan.cleaned_query,
            category=fts_cat,
            limit=limit,
        )
        for r in fts_hits:
            p_str = str(r.get("path", ""))
            if not p_str:
                continue
            entry = get_or_create(p_str, r)
            raw_rank = float(r.get("rank") or 0.0)
            norm_bm25 = 1.0 / (1.0 + abs(raw_rank))
            entry["bm25_score"] = max(entry["bm25_score"], norm_bm25)
            if r.get("snippet"):
                entry["snippet"] = r["snippet"]
            entry["reasons"].append("Lexical FTS match")

        # ── Branch 3: Exact Terms & Acronym Expansion ─────────────────
        if plan.search_terms:
            for term in plan.search_terms[:6]:
                sub_hits = self.database.keyword_search(term, category=fts_cat, limit=20)
                for r in sub_hits:
                    p_str = str(r.get("path", ""))
                    if not p_str:
                        continue
                    entry = get_or_create(p_str, r)
                    entry["bm25_score"] = max(entry["bm25_score"], 0.7)
                    entry["reasons"].append(f"Matched term '{term}'")

        # ── Branch 4: DISABLED IN THIS DIAGNOSTIC (file_score = 0.0) ───
        # Note: We do NOT apply filename bonus in this diagnostic experiment!
        for p_str, entry in candidates.items():
            entry["file_score"] = 0.0

        # ── Branch 5: Dense Vector Retrieval (if VectorStore active) ──
        if self.embedding_provider is not None and self.vector_store is not None:
            try:
                q_vec = self.embedding_provider.embed_text(plan.cleaned_query)
                v_matches = self.vector_store.query_nearest(
                    q_vec,
                    model_name=self.embedding_provider.model_name,
                    k=limit,
                    threshold=0.25,
                )
                for vm in v_matches:
                    file_rec = self.database.get_file_by_id(vm.entity_id) if hasattr(self.database, "get_file_by_id") else None
                    if file_rec:
                        p_str = str(file_rec.get("path", ""))
                        entry = get_or_create(p_str, file_rec)
                        entry["sem_score"] = max(entry["sem_score"], float(vm.similarity))
                        entry["reasons"].append(f"Semantic similarity ({vm.similarity:.2f})")
            except Exception:
                pass

        # ── Re-normalized Linear Score Fusion without Filename Weight ──
        if plan.is_visual:
            # Original: clip=0.60, bm25=0.15, sem=0.10, file=0.15 (sum non-file=0.85)
            w_clip = 0.60 / 0.85
            w_bm25 = 0.15 / 0.85
            w_sem  = 0.10 / 0.85
        elif plan.is_academic:
            # Original: clip=0.00, bm25=0.35, sem=0.20, file=0.45 (sum non-file=0.55)
            w_clip = 0.00
            w_bm25 = 0.35 / 0.55
            w_sem  = 0.20 / 0.55
        else:
            # Original: clip=0.15, bm25=0.35, sem=0.25, file=0.25 (sum non-file=0.75)
            w_clip = 0.15 / 0.75
            w_bm25 = 0.35 / 0.75
            w_sem  = 0.25 / 0.75

        final_results: list[dict] = []
        for p_str, entry in candidates.items():
            rec = entry["record"]

            if user_category:
                cat_norm = user_category.strip().lower()
                rec_cat = str(rec.get("file_type", "")).strip().lower()
                if rec_cat and rec_cat != cat_norm:
                    continue

            if plan.ext_filter and not p_str.lower().endswith(plan.ext_filter):
                continue

            score = (
                w_clip * entry["clip_score"]
                + w_bm25 * entry["bm25_score"]
                + w_sem * entry["sem_score"]
            )
            score = max(0.0, min(1.0, score))

            rec["rank"] = -score
            rec["relevance_score"] = score
            rec["match_evidence"] = {
                "relevance_score": score,
                "lexical": entry["bm25_score"],
                "semantic": entry["sem_score"],
                "visual": entry["clip_score"],
                "filename": 0.0,
            }
            final_results.append(rec)

        final_results.sort(key=lambda x: (float(x.get("rank", 0.0)), str(x.get("path", ""))))
        return final_results[:limit]


def run_diagnostic_no_filename():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "diag_nofname.db"
        db = Database(db_path)
        vstore = SQLiteFlatVectorStore(db_path)
        embed_provider = SentenceTransformerProvider()

        total_bytes = build_ablation_corpus(db, tmpdir)

        all_files = db.get_recent_files(limit=50)
        file_ids = [int(f["id"]) for f in all_files]
        file_texts = [f"{f['filename']} {f.get('extracted_text','')}" for f in all_files]
        vectors = embed_provider.embed_batch(file_texts)
        vstore.add_vectors("file", file_ids, vectors, model_name=embed_provider.model_name)

        agent = NoFilenameAgent(db, embedding_provider=embed_provider, vector_store=vstore)

        conditions = BenchmarkConditions(
            corpus_size_bytes=total_bytes,
            num_indexed_files=len(all_files),
            num_text_chunks=len(all_files),
            num_image_embeddings=sum(1 for f in all_files if f.get("extension") in (".png", ".jpg")),
            cold_warm_state="warm",
            query_count=25,
        )

        harness = EvaluationHarness(GOLD_BENCHMARK_QUERIES)

        print("\n" + "=" * 80)
        print("DIAGNOSTIC EXPERIMENT 1: RETRIEVAL WITHOUT FILENAME MATCHING BONUS")
        print("=" * 80)

        report = harness.run_benchmark(
            lambda q, cat: agent.search(q, user_category=cat, limit=10),
            conditions=conditions,
        )

        print(report.summary_table())

        print("\n" + "=" * 115)
        print(f"{'QID':<5} | {'Query':<35} | {'Target File':<35} | {'Rank':<6} | {'Hit@1':<6} | {'RR':<6} | {'nDCG@10':<8}")
        print("-" * 115)
        for r in report.query_results:
            rank_str = str(r.first_relevant_rank) if r.first_relevant_rank is not None else "None"
            print(f"{r.query_id:<5} | {r.query_text[:35]:<35} | {r.target_files[0][:35]:<35} | {rank_str:<6} | {r.hit_1:<6.1f} | {r.reciprocal_rank:<6.3f} | {r.ndcg_10:<8.4f}")
        print("=" * 115)

        return report


if __name__ == "__main__":
    run_diagnostic_no_filename()
