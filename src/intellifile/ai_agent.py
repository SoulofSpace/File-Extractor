"""
ai_agent.py — Intelligent Natural Language & Multimodal Hybrid Search Engine
Translates human conversational queries into precision file searches:
  • "i need my DBMS DA 3" -> Finds Database Management Systems Digital Assignment / Lab 3
  • "crimson crawlers" / "red spider logo" -> Finds esports red spider logo image via CLIP Vision
  • "flow diagram for how to start a startup sort of stuff" -> Finds startup flowcharts & diagrams
  • "2 persons taking selfie with both in red dress" -> Activates multimodal visual semantic search
  • Automatically expands university/technical acronyms (DBMS, DA, LA, OS, DSA, CN)
  • Implements calibrated Linear Score Fusion and structured Match Evidence
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
import numpy as np

logger = logging.getLogger(__name__)

from .database import Database
from .domain.interfaces import MatchEvidence, TextEmbeddingProvider, VectorStore
from .domain.composition import CandidateEvidence, CompositionalQuery
from .compositional_evaluator import CompositionalEvaluator
from .query_planner import QueryPlan, QueryPlanner, ACRONYM_MAP, ASSIGNMENT_REGEX, COMPOUND_PAIRS, CONVERSATIONAL_FILLERS, decompose_compositional_query
from .reranker import CandidateReranker
from .vision_search import search_images_with_clip


class AIAgent:
    """
    Intelligent Multimodal Agent connecting conversational queries to local files
    through semantic parsing, acronym expansion, dense vector retrieval, and CLIP vision.
    """

    def __init__(
        self,
        database: Database,
        embedding_provider: Optional[TextEmbeddingProvider] = None,
        vector_store: Optional[VectorStore] = None,
        query_planner: Optional[QueryPlanner] = None,
        reranker: Optional[CandidateReranker] = None,
        compositional_evaluator: Optional[CompositionalEvaluator] = None,
    ):
        self.database = database
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store
        self.query_planner = query_planner or QueryPlanner()
        self.reranker = reranker or CandidateReranker()
        self.compositional_evaluator = compositional_evaluator or CompositionalEvaluator()

    def parse_query(self, query: str) -> QueryPlan:
        """Parse raw query into structured QueryPlan using QueryPlanner."""
        return self.query_planner.parse_query(query)


    def search(
        self,
        query: str,
        user_category: Optional[str] = None,
        limit: int = 45,
        debug: bool = False,
        rerank: bool = False,
    ) -> list[dict]:

        plan = self.parse_query(query)

        # Candidate registry: path -> {record, scores: {bm25, sem, clip, file, ocr, metadata}, reasons, snippet}
        candidates: Dict[str, Dict[str, Any]] = {}

        def get_or_create(path_str: str, file_dict: dict) -> Dict[str, Any]:
            if path_str not in candidates:
                candidates[path_str] = {
                    "record": dict(file_dict),
                    "file_score": 0.0,
                    "bm25_score": 0.0,
                    "ocr_score": 0.0,
                    "sem_score": 0.0,
                    "clip_score": 0.0,
                    "vlm_score": 0.0,
                    "metadata_score": 0.0,
                    "subject_match": 0.0,
                    "attribute_match": 0.0,
                    "clothing_match": 0.0,
                    "object_match": 0.0,
                    "action_match": 0.0,
                    "relationship_match": 0.0,
                    "scene_match": 0.0,
                    "coordination_score": 0.0,
                    "contradiction_penalty": 0.0,
                    "reasons": [],
                    "snippet": file_dict.get("snippet", ""),
                }
            return candidates[path_str]

        # ── Branch 1a: Deep Multimodal CLIP Vision Search ─────────────
        if user_category:
            should_clip = (user_category.strip().upper() == "IMAGE")
        else:
            # Enable visual search if query is visual or general (not strictly academic notes/assignments)
            should_clip = plan.is_visual or not plan.is_academic
        if should_clip:
            all_images = self.database.get_recent_files(category="Image", limit=150)
            if all_images:
                clip_hits = search_images_with_clip(
                    plan.cleaned_query,
                    all_images,
                    threshold=0.19,
                    limit=25,
                )
                for hit in clip_hits:
                    p_str = str(hit.get("path", ""))
                    if not p_str:
                        continue
                    entry = get_or_create(p_str, hit)
                    # Normalize CLIP cosine similarity [0.19 - 0.36] -> [0.5 - 1.0]
                    raw_sim = float(hit.get("rank", 0.0))
                    if raw_sim < 0:
                        raw_sim = -raw_sim  # rank is -sim in vision_search
                    sim_norm = min(1.0, max(0.0, (raw_sim - 0.18) / 0.16))
                    entry["clip_score"] = sim_norm
                    entry["reasons"].append(f"Visual CLIP match ({sim_norm:.2f})")

        # ── Branch 1b: Universal Document & Visual Understanding (V3) ──
        du_records_by_file_id: Dict[int, dict] = {}
        du_file_ids: set = set()
        if hasattr(self.database, "connection"):
            try:
                with self.database.connection() as conn:
                    du_rows = conn.execute("SELECT * FROM document_understanding").fetchall()
                    for r in du_rows:
                        d = dict(r)
                        fid = d.get("file_id")
                        if fid:
                            du_records_by_file_id[fid] = d
                            du_file_ids.add(fid)
            except Exception:
                pass

        if hasattr(self.database, "search_document_understanding"):
            try:
                du_hits = self.database.search_document_understanding(plan.cleaned_query, limit=50)
                for du in du_hits:
                    p_str = str(du.get("path", ""))
                    if not p_str:
                        continue
                    get_or_create(p_str, du)
            except Exception as du_err:
                logger.debug("Document understanding search skipped: %s", du_err)


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
            # FTS rank: negative or close to 0
            raw_rank = float(r.get("rank") or 0.0)
            norm_bm25 = 1.0 / (1.0 + abs(raw_rank))
            entry["bm25_score"] = max(entry["bm25_score"], norm_bm25)
            if r.get("ocr_text"):
                entry["ocr_score"] = max(entry["ocr_score"], norm_bm25)
            if r.get("snippet"):
                entry["snippet"] = r["snippet"]
            entry["reasons"].append("Lexical FTS match")

        # ── Branch 3: Exact Terms & Acronym Expansion ─────────────────
        if plan.search_terms:
            for term in plan.search_terms[:6]:
                if term.lower() == plan.cleaned_query.lower():
                    continue
                sub_hits = self.database.keyword_search(term, category=fts_cat, limit=20)
                for r in sub_hits:
                    p_str = str(r.get("path", ""))
                    if not p_str:
                        continue
                    entry = get_or_create(p_str, r)
                    entry["bm25_score"] = max(entry["bm25_score"], 0.7)
                    if r.get("ocr_text"):
                        entry["ocr_score"] = max(entry["ocr_score"], 0.7)
                    entry["reasons"].append(f"Matched term '{term}'")

        # ── Branch 4: Filename & Entity Match Bonus ───────────────────
        clean_low = plan.cleaned_query.lower()
        clean_q_tokens = [t for t in re.sub(r"[^\w\s]", " ", clean_low).split() if len(t) > 1]
        clean_q_norm = " ".join(clean_q_tokens)

        for p_str, entry in candidates.items():
            rec = entry["record"]
            fname = str(rec.get("filename", Path(p_str).name)).lower()
            fname_tokens = [t for t in re.sub(r"[^\w\s]", " ", fname).split() if len(t) > 1]
            fname_norm = " ".join(fname_tokens)
            content = str(rec.get("extracted_text", "")).lower()

            f_score = 0.0
            if clean_q_norm and clean_q_norm in fname_norm:
                f_score = 1.0
                entry["reasons"].append("Exact filename match")
            elif clean_q_tokens and all(t in fname_tokens for t in clean_q_tokens):
                f_score = 0.95
                entry["reasons"].append("All query terms in filename")
            else:
                for term in plan.search_terms:
                    t_low = term.lower()
                    t_tokens = [t for t in re.sub(r"[^\w\s]", " ", t_low).split() if len(t) > 1]
                    t_norm = " ".join(t_tokens)
                    if t_norm and t_norm in fname_norm:
                        f_score = max(f_score, 0.8)
                        entry["reasons"].append(f"Filename contains '{term}'")
                        break
                    elif t_low in content:
                        f_score = max(f_score, 0.4)

            entry["file_score"] = f_score

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

        # ── Branch 6: Structured Compositional Role Evaluation ───────
        cq = plan.compositional_query or decompose_compositional_query(plan.cleaned_query)
        for p_str, entry in candidates.items():
            rec = entry["record"]
            rec_id = rec.get("id") or rec.get("file_id")
            du_data = du_records_by_file_id.get(rec_id)
            if du_data:
                cand_ev = CandidateEvidence.from_du_dict(du_data, path=p_str)
            else:
                cand_ev = CandidateEvidence(path=p_str, file_id=rec_id, has_vlm=False)

            c_score = self.compositional_evaluator.evaluate(cq, cand_ev)
            entry["subject_match"] = c_score.subject_match
            entry["attribute_match"] = c_score.attribute_match
            entry["clothing_match"] = c_score.clothing_match
            entry["object_match"] = c_score.object_match
            entry["action_match"] = c_score.action_match
            entry["relationship_match"] = c_score.relationship_match
            entry["scene_match"] = c_score.scene_match
            entry["coordination_score"] = c_score.coordination_score
            entry["contradiction_penalty"] = c_score.contradiction_penalty
            entry["vlm_score"] = c_score.vlm_score
            if c_score.vlm_score > 0.15:
                entry["reasons"].append(f"Visual understanding ({c_score.vlm_score:.2f})")

        # ── Linear Score Fusion & Structured Match Evidence ───────────
        # Determine weights based on query intent
        if plan.is_academic:
            w_clip, w_bm25, w_sem, w_file = 0.00, 0.35, 0.20, 0.45
        elif plan.is_visual:
            w_clip, w_bm25, w_sem, w_file = 0.60, 0.15, 0.10, 0.15
        else:
            w_clip, w_bm25, w_sem, w_file = 0.15, 0.35, 0.25, 0.25

        final_results: list[dict] = []
        for p_str, entry in candidates.items():
            rec = entry["record"]

            # Filter by category if explicitly requested by user
            if user_category:
                cat_norm = user_category.strip().lower()
                rec_cat = str(rec.get("file_type", "")).strip().lower()
                if rec_cat and rec_cat != cat_norm:
                    continue

            # Filter by extension if specified in query
            if plan.ext_filter and not p_str.lower().endswith(plan.ext_filter):
                continue

            # Compute baseline fused relevance score in [0.0, 1.0]
            base_score = (
                w_clip * entry["clip_score"]
                + w_bm25 * entry["bm25_score"]
                + w_sem * entry["sem_score"]
                + w_file * entry["file_score"]
            )
            vlm_s = entry.get("vlm_score", 0.0)
            coord = entry.get("coordination_score", 0.0)
            contra = entry.get("contradiction_penalty", 0.0)

            rec_id = rec.get("id") or rec.get("file_id")
            if vlm_s > 0.05 and coord >= 0.25:
                # Structured VLM evidence blending:
                # Blends proportionally with coordination up to 35%
                w_vlm = 0.35 * coord
                score = w_vlm * vlm_s + (1.0 - w_vlm) * base_score
            else:
                score = base_score
                if rec_id in du_file_ids and entry["clip_score"] > 0.0 and plan.is_visual and coord < 0.25:
                    # Negative confirmation: VLM analyzed image and confirmed no match for visual roles
                    score = score * 0.85

            # Contradiction suppression: if candidate contradicts query requirements
            if contra > 0.0:
                score = score * max(0.15, (1.0 - 0.60 * contra))
            score = max(0.0, min(1.0, score))

            # Deduplicate reasons
            unique_reasons = []
            seen_r = set()
            if plan.explanation and (entry["file_score"] > 0 or entry["bm25_score"] > 0):
                unique_reasons.append(plan.explanation)
                seen_r.add(plan.explanation)

            for r in entry["reasons"]:
                if r not in seen_r:
                    seen_r.add(r)
                    unique_reasons.append(r)

            evidence = MatchEvidence(
                relevance_score=round(score, 3),
                lexical_score=round(entry["bm25_score"], 3),
                semantic_score=round(entry["sem_score"], 3),
                visual_score=round(entry["clip_score"], 3),
                vlm_score=round(vlm_s, 3),
                filename_score=round(entry["file_score"], 3),
                ocr_score=round(entry["ocr_score"], 3),
                metadata_score=round(entry["metadata_score"], 3),
                subject_match=round(entry.get("subject_match", 0.0), 3),
                attribute_match=round(entry.get("attribute_match", 0.0), 3),
                clothing_match=round(entry.get("clothing_match", 0.0), 3),
                object_match=round(entry.get("object_match", 0.0), 3),
                action_match=round(entry.get("action_match", 0.0), 3),
                relationship_match=round(entry.get("relationship_match", 0.0), 3),
                scene_match=round(entry.get("scene_match", 0.0), 3),
                coordination_score=round(coord, 3),
                contradiction_penalty=round(contra, 3),
                explanation=" · ".join(unique_reasons[:3]) if unique_reasons else "Matching file content",
                snippet=entry["snippet"],
            )

            rec["rank"] = -score  # Negative so sort ascending puts highest score first
            rec["relevance_score"] = score
            rec["ai_badge"] = evidence.formatted_badge()
            rec["ai_explanation"] = evidence.explanation
            rec["snippet"] = evidence.snippet
            rec["match_evidence"] = evidence.debug_dict()
            rec["match_evidence"]["filename"] = entry["file_score"]
            rec["match_evidence"]["lexical"] = entry["bm25_score"]
            rec["match_evidence"]["ocr"] = entry["ocr_score"]
            rec["match_evidence"]["semantic"] = entry["sem_score"]
            rec["match_evidence"]["visual"] = entry["clip_score"]
            rec["match_evidence"]["vlm"] = vlm_s
            final_results.append(rec)

        # Deterministic sorting: primary sort by rank (negative score), secondary tie-breaker by path
        final_results.sort(key=lambda x: (float(x.get("rank", 0.0)), str(x.get("path", ""))))

        # Optional second-stage reranking on top candidates
        if rerank and self.reranker is not None:
            final_results = self.reranker.rerank(query, final_results, top_k=min(5, len(final_results)))

        if debug:
            print(f"\nQUERY:\n\"{query}\"")
            for r in final_results[:10]:
                fn = r.get("filename", Path(r.get("path", "")).name)
                me = r.get("match_evidence", {})
                print(f"\nRESULT: {fn}\n")
                print("Scores:")
                print(f"  subject_match      = {me.get('subject_match', 0.0):.2f}")
                print(f"  attribute_match    = {me.get('attribute_match', 0.0):.2f}")
                print(f"  clothing_match     = {me.get('clothing_match', 0.0):.2f}")
                print(f"  object_match       = {me.get('object_match', 0.0):.2f}")
                print(f"  action_match       = {me.get('action_match', 0.0):.2f}")
                print(f"  relationship_match = {me.get('relationship_match', 0.0):.2f}")
                print(f"  scene_match        = {me.get('scene_match', 0.0):.2f}")
                print(f"  CLIP               = {me.get('CLIP', 0.0):.2f}")
                print(f"  SBERT              = {me.get('SBERT', 0.0):.2f}")
                print(f"  BM25               = {me.get('BM25', 0.0):.2f}")
                print(f"  OCR                = {me.get('OCR', 0.0):.2f}")
                print(f"  metadata           = {me.get('metadata', 0.0):.2f}")
                print(f"  coordination       = {me.get('coordination', 0.0):.2f}")
                print(f"  contradiction      = {me.get('contradiction', 0.0):.2f}")
                print(f"  final_score        = {r.get('relevance_score', 0.0):.2f}")

        return final_results[:limit]

