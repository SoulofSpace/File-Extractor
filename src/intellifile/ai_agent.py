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
from .query_planner import QueryPlan, QueryPlanner, ACRONYM_MAP, ASSIGNMENT_REGEX, COMPOUND_PAIRS, CONVERSATIONAL_FILLERS
from .reranker import CandidateReranker
from .vision_search import search_images_with_clip

# Conversational stopwords to strip
CONVERSATIONAL_FILLERS = [
    r"^i need (my|the|a)?\s*",
    r"^can you (find|give|get|show) (me)?\s*",
    r"^where is (my|the|a)?\s*",
    r"^give me (my|the|a)?\s*",
    r"^show (me)?\s*",
    r"^find (me)?\s*",
    r"^looking for\s*",
    r"^search for\s*",
    r"\s*sort of stuff$",
    r"\s*and stuff$",
    r"\s*sort of thing$",
    r"\s*for me$",
    r"\s*please$",
]

# Academic & Technical Acronym expansions
ACRONYM_MAP: dict[str, list[str]] = {
    "dbms": ["DBMS", "Database Management Systems", "Database", "SQL"],
    "os": ["Operating Systems", "OS", "BACSE106"],
    "cn": ["Computer Networks", "Networking"],
    "dsa": ["Data Structures", "Algorithms", "DSA"],
    "ai": ["Artificial Intelligence", "Machine Learning"],
    "ml": ["Machine Learning", "Model"],
    "oops": ["Object Oriented Programming", "Java", "C++"],
    "daa": ["Design and Analysis of Algorithms"],
    "toc": ["Theory of Computation"],
    "id": ["ID", "Identity", "Identification", "ID Card"],
}

ASSIGNMENT_REGEX = re.compile(r"\b(da|la|lab|assignment|assessment)\s*[-_]?\s*(\d+)\b", re.IGNORECASE)

# Standard compound word variations (open/closed/hyphenated)
COMPOUND_PAIRS: dict[str, str] = {
    "timetable": "time table",
    "time table": "timetable",
    "flowchart": "flow chart",
    "flow chart": "flowchart",
    "screenshot": "screen shot",
    "screen shot": "screenshot",
    "wireframe": "wire frame",
    "wire frame": "wireframe",
}

VISUAL_TRIGGERS = {
    # Person / Portrait / Clothing
    "selfie", "person", "persons", "people", "man", "guy", "woman", "girl", "boy",
    "red dress", "blue dress", "dress", "shirt", "wearing", "wear", "clothes", "clothing",
    "photo", "picture", "camera", "smile", "beach", "sunset", "portrait",
    # Visual Documents / Schedules / Identity
    "timetable", "time table", "schedule", "routine",
    "id card", "identity card", "student id", "college id", "card",
    "certificate", "receipt", "invoice", "bill", "ticket",
    # Diagrams & Graphics
    "flow diagram", "flowchart", "flow chart", "diagram", "wireframe", "wire frame",
    "screenshot", "screen shot", "startup",
    "logo", "spider", "crimson", "crawler", "crawlers", "drawing", "illustration",
    "artwork", "clipart", "sketch", "graphic", "emblem", "wallpaper", "chart", "graph",
}


@dataclass
class QueryPlan:
    raw_query: str
    cleaned_query: str
    is_visual: bool = False
    is_academic: bool = False
    target_category: Optional[str] = None
    search_terms: list[str] = field(default_factory=list)
    explanation: str = ""
    size_filter: Optional[Tuple[str, int]] = None       # ('gt'/'lt', bytes)
    ext_filter: Optional[str] = None


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
    ):
        self.database = database
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store
        self.query_planner = query_planner or QueryPlanner()
        self.reranker = reranker or CandidateReranker()

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
        if hasattr(self.database, "search_document_understanding"):
            try:
                du_hits = self.database.search_document_understanding(plan.cleaned_query, limit=30)
                for du in du_hits:
                    p_str = str(du.get("path", ""))
                    if not p_str:
                        continue
                    entry = get_or_create(p_str, du)
                    entry["vlm_score"] = max(entry["vlm_score"], 0.95)
                    d_type = du.get("document_type", "document")
                    t_name = du.get("title") or du.get("event_name") or ""
                    reason_desc = f"Visual understanding: {d_type}" + (f" '{t_name}'" if t_name else "")
                    entry["reasons"].append(reason_desc)
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

        # ── Linear Score Fusion & Structured Match Evidence ───────────
        # Determine weights based on query intent
        if plan.is_visual:
            w_clip, w_bm25, w_sem, w_file = 0.60, 0.15, 0.10, 0.15
        elif plan.is_academic:
            w_clip, w_bm25, w_sem, w_file = 0.00, 0.35, 0.20, 0.45
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
            if vlm_s > 0.0:
                # If VLM document understanding matched, blend with 35% weight
                w_vlm = 0.35
                score = w_vlm * vlm_s + (1.0 - w_vlm) * base_score
            else:
                score = base_score
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
                explanation=" · ".join(unique_reasons[:3]) if unique_reasons else "Matching file content",
                snippet=entry["snippet"],
            )

            rec["rank"] = -score  # Negative so sort ascending puts highest score first
            rec["relevance_score"] = score
            rec["ai_badge"] = evidence.formatted_badge()
            rec["ai_explanation"] = evidence.explanation
            rec["snippet"] = evidence.snippet
            rec["match_evidence"] = {
                "relevance_score": score,
                "filename": entry["file_score"],
                "lexical": entry["bm25_score"],
                "ocr": entry["ocr_score"],
                "semantic": entry["sem_score"],
                "visual": entry["clip_score"],
                "vlm": vlm_s,
                "metadata": entry["metadata_score"],
            }
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
                print(f"\nRESULT:\n{fn}\n")
                print("Scores:")
                print(f"  exact_filename = {me.get('filename', 0.0):.2f}")
                print(f"  BM25           = {me.get('lexical', 0.0):.2f}")
                print(f"  OCR            = {me.get('ocr', 0.0):.2f}")
                print(f"  SBERT          = {me.get('semantic', 0.0):.2f}")
                print(f"  CLIP           = {me.get('visual', 0.0):.2f}")
                print(f"  VLM            = {me.get('vlm', 0.0):.2f}")
                print(f"  metadata       = {me.get('metadata', 0.0):.2f}")
                print(f"  final          = {r.get('relevance_score', 0.0):.2f}")

        return final_results[:limit]

