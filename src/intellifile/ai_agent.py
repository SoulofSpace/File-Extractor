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
from .universal_query_planner import UniversalQueryPlanner, UniversalSearchPlan
from .person_service import PersonService
from .sarvam_service import SarvamService
from .privacy_engine import PrivacyEngine

CATEGORY_EXTS_MAP = {
    "document": {".pdf", ".docx", ".doc", ".txt", ".md", ".rtf", ".pptx", ".ppt", ".xlsx", ".xls", ".csv", ".tsv", ".odt", ".ods", ".epub"},
    "documents": {".pdf", ".docx", ".doc", ".txt", ".md", ".rtf", ".pptx", ".ppt", ".xlsx", ".xls", ".csv", ".tsv", ".odt", ".ods", ".epub"},
    "image": {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".gif", ".svg", ".ico"},
    "images": {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".gif", ".svg", ".ico"},
    "video": {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v"},
    "videos": {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v"},
    "audio": {".mp3", ".wav", ".flac", ".aac", ".m4a", ".ogg", ".wma"},
    "code": {".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".c", ".cpp", ".h", ".cs", ".go", ".rs", ".html", ".css", ".json", ".xml", ".yaml", ".yml", ".sql", ".sh", ".bat"},
    "archive": {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz"},
    "archives": {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz"},
}


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
        universal_query_planner: Optional[UniversalQueryPlanner] = None,
        person_service: Optional[PersonService] = None,
        sarvam_service: Optional[SarvamService] = None,
        privacy_engine: Optional[PrivacyEngine] = None,
    ):
        self.database = database
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store
        self.query_planner = query_planner or QueryPlanner()
        self.reranker = reranker or CandidateReranker()
        self.compositional_evaluator = compositional_evaluator or CompositionalEvaluator()
        self.universal_query_planner = universal_query_planner
        self.person_service = person_service
        self.sarvam_service = sarvam_service
        self.privacy_engine = privacy_engine or (PrivacyEngine(database) if database else None)

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
        privacy_scope: str = "NORMAL",
        is_authenticated: bool = False,
        privacy_token: Optional[str] = None,
    ) -> list[dict]:

        # Validate privacy token if provided
        if privacy_token and self.privacy_engine:
            if self.privacy_engine.validate_session(privacy_token):
                is_authenticated = True
                privacy_scope = "PRIVATE"

        # ── V4 Input Processing: Multilingual / Code-mixed translation ────────
        working_query = query
        original_query = query
        was_translated = False
        detected_lang = None

        if self.sarvam_service and self.sarvam_service.is_configured and self.sarvam_service.is_multilingual_enabled:
            try:
                res = self.sarvam_service.translate_query_details(query)
                if res.was_translated and res.translated_text and res.translated_text.strip():
                    working_query = res.translated_text.strip()
                    was_translated = True
                    detected_lang = res.source_language
            except Exception as e:
                logger.warning("Sarvam translation error: %s. Using original query.", e)
                working_query = query

        self.last_original_query = original_query
        self.last_translated_query = working_query
        self.last_was_translated = was_translated
        self.last_detected_language = detected_lang

        # ── V4 Universal Query Planning ───────────────────────────────────────
        if self.universal_query_planner is None and self.database:
            self.universal_query_planner = UniversalQueryPlanner(self.database)

        v4_plan = (
            self.universal_query_planner.plan_query(
                working_query,
                original_query=original_query,
                was_translated=was_translated,
                source_language=detected_lang,
            )
            if self.universal_query_planner
            else None
        )

        # V3 Query plan for legacy scoring compatibility
        v3_q = (v4_plan.cleaned_query if v4_plan and v4_plan.cleaned_query else working_query)
        plan = self.parse_query(v3_q)

        # Candidate registry: path -> {record, scores: {bm25, sem, clip, file, ocr, metadata, person, date, category}, reasons, snippet}
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
                    "person_score": 0.0,
                    "date_score": 0.0,
                    "category_score": 0.0,
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

        # ── Branch 0: V4 Person/Entity Retrieval (Requirement 13) ────────────
        if v4_plan and v4_plan.is_person_search and v4_plan.person_name:
            target_p = self.database.find_person_by_name_or_alias(v4_plan.person_name)
            if not target_p:
                for kp in self.database.list_persons(include_clusters=False, privacy_scope=privacy_scope):
                    if v4_plan.person_name.lower() in kp["name"].lower():
                        target_p = kp
                        break
            if target_p:
                p_files = self.database.get_person_files(target_p["id"], privacy_scope=privacy_scope)
                for pf in p_files:
                    p_str = str(pf.get("path", ""))
                    if not p_str:
                        continue
                    entry = get_or_create(p_str, pf)
                    conf = float(pf.get("confidence") or 0.95)
                    entry["person_score"] = max(entry["person_score"], conf)
                    link_tp = pf.get("link_type", "face")
                    entry["reasons"].append(f"Person match: {target_p['name']} ({link_tp})")

        # ── Branch 1a: Deep Multimodal CLIP Vision Search ─────────────
        if user_category:
            should_clip = (user_category.strip().upper() == "IMAGE")
        elif v4_plan and v4_plan.file_type:
            should_clip = (v4_plan.file_type == "image")
        else:
            # Enable visual search if query is visual or general (not strictly academic notes/assignments)
            should_clip = plan.is_visual or (v4_plan and bool(v4_plan.visual_concepts)) or not plan.is_academic
        if should_clip:
            all_images = [img for img in self.database.get_recent_files(category="Image", limit=150) if Path(img.get("path", "")).exists()]
            if all_images:
                clip_q = plan.cleaned_query or (v4_plan.cleaned_query if v4_plan else "")
                clip_hits = search_images_with_clip(
                    clip_q,
                    all_images,
                    threshold=0.18,
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
                    file_rec = None
                    fid = du.get("file_id") or du.get("id")
                    if fid and hasattr(self.database, "get_file_by_id"):
                        file_rec = self.database.get_file_by_id(fid)
                    candidate_dict = dict(file_rec) if file_rec else dict(du)
                    get_or_create(p_str, candidate_dict)
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

        # ── V4 Date Evaluation (Requirement 16) ──────────────────────
        if v4_plan and (v4_plan.date_start or v4_plan.date_end):
            for p_str, entry in candidates.items():
                rec = entry["record"]
                f_date = rec.get("capture_date")
                if not f_date and rec.get("modified_at"):
                    import datetime
                    try:
                        f_date = datetime.datetime.fromtimestamp(rec["modified_at"]).strftime("%Y-%m-%d")
                    except Exception:
                        pass

                if f_date:
                    in_range = True
                    if v4_plan.date_start and f_date < v4_plan.date_start:
                        in_range = False
                    if v4_plan.date_end and f_date > v4_plan.date_end:
                        in_range = False
                    if in_range:
                        entry["date_score"] = 1.0
                        entry["metadata_score"] = max(entry["metadata_score"], 0.9)
                        entry["reasons"].append(f"Date match ({f_date})")
                    else:
                        entry["date_score"] = -1.0

        # ── V4 Document Type & Category Evaluation (Requirement 17) ──
        if v4_plan and (v4_plan.category or v4_plan.document_type):
            target_cat = (v4_plan.category or "").lower()
            target_dt = (v4_plan.document_type or "").lower()
            for p_str, entry in candidates.items():
                rec = entry["record"]
                r_cat = str(rec.get("category_v4") or rec.get("category") or "").lower()
                r_dt = str(rec.get("document_type") or "").lower()
                r_name = str(rec.get("filename") or Path(p_str).name).lower()
                if target_dt and (target_dt in r_dt or target_dt in r_name):
                    entry["category_score"] = max(entry.get("category_score", 0.0), 1.0)
                    entry["metadata_score"] = max(entry["metadata_score"], 0.95)
                    entry["reasons"].append(f"Doc type: {rec.get('document_type') or target_dt.title()}")
                elif target_cat and (target_cat in r_cat or target_cat in r_name):
                    entry["category_score"] = max(entry.get("category_score", 0.0), 0.8)
                    entry["metadata_score"] = max(entry["metadata_score"], 0.85)
                    entry["reasons"].append(f"Category: {rec.get('category_v4') or target_cat.title()}")

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
            if not Path(p_str).exists():
                continue
            rec = entry["record"]

            # Filter by category if explicitly requested by user
            if user_category and user_category.strip().upper() != "ALL":
                cat_norm = user_category.strip().lower()
                cat_exts = CATEGORY_EXTS_MAP.get(cat_norm, set())
                rec_ext = str(rec.get("extension", "")).strip().lower()
                rec_type = str(rec.get("file_type", "")).strip().lower()
                rec_cat = str(rec.get("category", "")).strip().lower()

                matches_cat = (
                    (rec_ext in cat_exts)
                    or (cat_norm in rec_type)
                    or (cat_norm in rec_cat)
                    or (cat_norm in ("document", "documents") and any(w in rec_type for w in ("pdf", "word", "document", "text", "sheet", "presentation", "markdown")))
                    or (cat_norm in ("image", "images") and any(w in rec_type for w in ("image", "photo", "picture", "jpeg", "png", "webp", "gif")))
                    or (cat_norm in ("video", "videos") and any(w in rec_type for w in ("video", "movie", "clip", "mp4", "mkv", "avi")))
                    or (cat_norm in ("audio", "audio") and any(w in rec_type for w in ("audio", "sound", "music", "song", "voice", "recording")))
                    or (cat_norm in ("code", "code") and any(w in rec_type for w in ("source", "code", "script", "program", "python", "javascript", "typescript", "c++", "java")))
                    or (cat_norm in ("archive", "archives") and any(w in rec_type for w in ("archive", "zip", "compressed", "tar", "rar")))
                )
                if not matches_cat:
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

            # V4 Person Match Fusion (Requirement 13)
            person_s = entry.get("person_score", 0.0)
            if v4_plan and v4_plan.is_person_search:
                if person_s > 0.0:
                    score = 0.55 * person_s + 0.45 * score
                else:
                    score = score * 0.40

            # V4 Date Match bonus / penalty
            date_s = entry.get("date_score", 0.0)
            if v4_plan and (v4_plan.date_start or v4_plan.date_end):
                if date_s > 0.0:
                    score = min(1.0, score * 1.35)
                elif date_s < 0.0:
                    score = score * 0.40

            # V4 Category / Doc Type bonus
            cat_s = entry.get("category_score", 0.0)
            if cat_s > 0.0:
                score = min(1.0, score * 1.25)

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
            rec["match_evidence"]["person"] = person_s

            if not rec.get("extension") and p_str:
                rec["extension"] = Path(p_str).suffix
            if not rec.get("filename") and p_str:
                rec["filename"] = Path(p_str).name

            if query != "*" and score <= 0.05:
                continue

            final_results.append(rec)

        # Deterministic sorting: primary sort by rank (negative score), secondary tie-breaker by path
        final_results.sort(key=lambda x: (float(x.get("rank", 0.0)), str(x.get("path", ""))))

        # Optional second-stage reranking on top candidates
        if rerank and self.reranker is not None:
            final_results = self.reranker.rerank(query, final_results, top_k=min(5, len(final_results)))

        # ── V4 Privacy Access Scope & Result Sanitization (Requirements 30 & 31) ──
        scoped_results = []
        for r in final_results:
            p_state = (r.get("privacy_state") or "NORMAL").upper()
            if p_state == "HIDDEN" and not is_authenticated:
                continue
            scoped_results.append(r)

        if self.privacy_engine is not None:
            sanitized_results = self.privacy_engine.sanitize_results(scoped_results, is_authenticated=is_authenticated)
        else:
            sanitized_results = scoped_results

        if debug:
            print(f"\nQUERY:\n\"{query}\"")
            for r in sanitized_results[:10]:
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

        return sanitized_results[:limit]

